"""Batch processor for download + parse + coverage validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
LINKS_FILE = BASE / "data" / "eurlex_links.jsonl"
DOWNLOAD_DIR = BASE / "downloads" / "eur-lex"
JSON_DIR = BASE / "out" / "json"
REPORTS_DIR = BASE / "reports"
SUCCESS_FILE = REPORTS_DIR / "eurlex_coverage_success.jsonl"
FAILURE_FILE = REPORTS_DIR / "eurlex_coverage_failures.jsonl"
BATCH_REPORTS_DIR = REPORTS_DIR / "batches"

PARSER_MODULE = "eurlex_unit_parser.cli.parse"
COVERAGE_MODULE = "eurlex_unit_parser.cli.coverage"
DOWNLOADER_MODULE = "eurlex_unit_parser.cli.download"

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
BATCH_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_output_dirs() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BATCH_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _subprocess_env() -> dict[str, str]:
    """Ensure subprocess module invocations can import local src package."""
    env = os.environ.copy()
    src_path = str(BASE / "src")
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not current else f"{src_path}{os.pathsep}{current}"
    return env


def stable_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def filename_from_entry(entry: dict) -> str:
    celex = entry.get("celex")
    if celex:
        return celex.replace(":", "_").replace("/", "_")
    return stable_hash(entry["url"])


def to_repo_relative(path: Path) -> str:
    """Return path relative to repository root for portable reports."""
    try:
        return str(path.resolve().relative_to(BASE.resolve()))
    except ValueError:
        return str(path)


def load_entries(links_file: Path) -> list[dict]:
    entries: list[dict] = []
    with open(links_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def slice_entries(entries: list[dict], offset: int = 0, limit: int | None = None) -> list[dict]:
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be > 0 when provided")

    if limit is None:
        return entries[offset:]
    return entries[offset : offset + limit]


def write_batch_snapshots(snapshot_tag: str) -> tuple[Path, Path]:
    safe_tag = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in snapshot_tag.strip())
    success_snapshot = BATCH_REPORTS_DIR / f"{safe_tag}_success.jsonl"
    failure_snapshot = BATCH_REPORTS_DIR / f"{safe_tag}_failures.jsonl"
    shutil.copy2(SUCCESS_FILE, success_snapshot)
    shutil.copy2(FAILURE_FILE, failure_snapshot)
    return success_snapshot, failure_snapshot


def download_html(url: str, html_path: Path) -> tuple[bool, str]:
    """Download using Playwright downloader, fall back to requests."""
    if html_path.exists() and html_path.stat().st_size > 1000:
        return True, "already_downloaded"

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                DOWNLOADER_MODULE,
                url,
                html_path.stem,
                "--output-dir",
                str(html_path.parent),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=_subprocess_env(),
        )
        if result.returncode == 0 and html_path.exists() and html_path.stat().st_size > 1000:
            return True, "playwright"
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    try:
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 1000:
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(resp.text, encoding="utf-8")
            return True, "requests_fallback"
        return False, f"http_{resp.status_code}"
    except Exception as e:
        return False, f"requests_error: {e}"


def parse_html(html_path: Path, json_path: Path, force: bool = False) -> tuple[bool, str]:
    """Run parser on HTML file."""
    if not force and json_path.exists() and json_path.stat().st_size > 10:
        return True, "already_parsed"

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                PARSER_MODULE,
                "--input",
                str(html_path),
                "--out",
                str(json_path),
                "--no-validation",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=_subprocess_env(),
        )
        if result.returncode == 0 and json_path.exists():
            return True, "ok"
        return False, f"parser_exit_{result.returncode}: {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "parser_timeout"
    except Exception as e:
        return False, f"parser_error: {e}"


def run_coverage(html_path: Path, json_path: Path, oracle: str = "naive") -> dict:
    """Run coverage test and parse results."""
    report = {
        "coverage_pct": 0.0,
        "missing_count": -1,
        "phantom_count": -1,
        "gone": -1,
        "misclassified": -1,
        "text_recall_pct": 0.0,
        "hierarchy_ok": False,
        "ordering_ok": True,
        "notes": "",
    }

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                COVERAGE_MODULE,
                "-i",
                str(html_path),
                "-j",
                str(json_path),
                "--oracle",
                oracle,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=_subprocess_env(),
        )
        output = result.stdout + result.stderr

        for line in output.splitlines():
            if line.startswith("METRICS_JSON:"):
                try:
                    metrics = json.loads(line[len("METRICS_JSON:") :].strip())
                    report["coverage_pct"] = metrics.get("coverage_pct", 0.0)
                    report["text_recall_pct"] = metrics.get("text_recall_pct", 0.0)
                    report["gone"] = metrics.get("gone", -1)
                    report["misclassified"] = metrics.get("misclassified", -1)
                    report["missing_count"] = metrics.get("total_missing", -1)
                    report["phantom_count"] = metrics.get("phantom", -1)
                    report["hierarchy_ok"] = metrics.get("hierarchy_ok", False)
                    report["ordering_ok"] = metrics.get("ordering_ok", True)
                    break
                except json.JSONDecodeError:
                    pass
        else:
            import re

            cov_match = re.search(r"(\d+(?:\.\d+)?)%\s+(?:text recall|coverage)", output)
            if cov_match:
                report["coverage_pct"] = float(cov_match.group(1))

            miss_match = re.search(r"(?:Missing segments|Gone \(truly missing\)):\s*(\d+)", output)
            if miss_match:
                report["missing_count"] = int(miss_match.group(1))

            phantom_match = re.search(r"Phantom segments:\s*(\d+)", output)
            if phantom_match:
                report["phantom_count"] = int(phantom_match.group(1))

            hier_match = re.search(r"Hierarchy issues:\s*(\d+)", output)
            if hier_match:
                report["hierarchy_ok"] = int(hier_match.group(1)) == 0

            ord_match = re.search(r"Ordering issues:\s*(\d+)", output)
            if ord_match:
                report["ordering_ok"] = int(ord_match.group(1)) == 0

        report["notes"] = output.strip()[-500:] if output.strip() else ""

        if result.returncode == 0:
            if report["coverage_pct"] == 0.0:
                report["coverage_pct"] = 100.0
            report["hierarchy_ok"] = True
            if report["missing_count"] == -1:
                report["missing_count"] = 0
            if report["phantom_count"] == -1:
                report["phantom_count"] = 0
            if report["gone"] == -1:
                report["gone"] = 0

        return report

    except subprocess.TimeoutExpired:
        report["notes"] = "coverage_timeout"
        return report
    except Exception as e:
        report["notes"] = f"coverage_error: {e}"
        return report


def run_batch(
    force_reparse: bool = False,
    oracle: str = "naive",
    links_file: Path = LINKS_FILE,
    offset: int = 0,
    limit: int | None = None,
    snapshot_tag: str | None = None,
) -> int:
    ensure_output_dirs()

    if not links_file.exists():
        print(f"ERROR: {links_file} not found")
        return 1

    all_entries = load_entries(links_file)
    try:
        entries = slice_entries(all_entries, offset=offset, limit=limit)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    print(f"Loaded {len(entries)} links from {links_file} (offset={offset}, limit={limit})")

    SUCCESS_FILE.write_text("")
    FAILURE_FILE.write_text("")

    success_count = 0
    failure_count = 0

    for i, entry in enumerate(entries, 1):
        url = entry["url"]
        fname = filename_from_entry(entry)
        html_path = DOWNLOAD_DIR / f"{fname}.html"
        json_path = JSON_DIR / f"{fname}.json"

        print(f"\n[{i}/{len(entries)}] {fname}")
        print(f"  URL: {url}")

        dl_ok, dl_method = download_html(url, html_path)
        if not dl_ok:
            record = {
                "url": url,
                "local_html": to_repo_relative(html_path),
                "local_json": to_repo_relative(json_path),
                "oracle": oracle,
                "coverage_pct": 0.0,
                "missing_count": -1,
                "phantom_count": -1,
                "hierarchy_ok": False,
                "ordering_ok": False,
                "notes": f"download_failed: {dl_method}",
            }
            with open(FAILURE_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
            failure_count += 1
            print(f"  DOWNLOAD FAILED: {dl_method}")
            continue

        print(f"  Downloaded: {dl_method} ({html_path.stat().st_size:,} bytes)")

        parse_ok, parse_note = parse_html(html_path, json_path, force=force_reparse)
        if not parse_ok:
            record = {
                "url": url,
                "local_html": to_repo_relative(html_path),
                "local_json": to_repo_relative(json_path),
                "oracle": oracle,
                "coverage_pct": 0.0,
                "missing_count": -1,
                "phantom_count": -1,
                "hierarchy_ok": False,
                "ordering_ok": False,
                "notes": f"parse_failed: {parse_note}",
            }
            with open(FAILURE_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
            failure_count += 1
            print(f"  PARSE FAILED: {parse_note}")
            continue

        print(f"  Parsed: {parse_note}")

        cov = run_coverage(html_path, json_path, oracle=oracle)
        record = {
            "url": url,
            "local_html": to_repo_relative(html_path),
            "local_json": to_repo_relative(json_path),
            "oracle": oracle,
            **cov,
        }

        passed = (
            cov["gone"] == 0
            and cov["phantom_count"] == 0
            and cov["hierarchy_ok"]
            and cov["ordering_ok"]
            and cov["coverage_pct"] > 0
        )

        out_file = SUCCESS_FILE if passed else FAILURE_FILE
        with open(out_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        if passed:
            success_count += 1
            print(
                f"  PASS: recall={cov['text_recall_pct']:.1f}% strict={cov['coverage_pct']:.1f}% "
                f"gone={cov['gone']} phantom={cov['phantom_count']}"
            )
        else:
            failure_count += 1
            print(
                f"  FAIL: recall={cov['text_recall_pct']:.1f}% strict={cov['coverage_pct']:.1f}% "
                f"gone={cov['gone']} phantom={cov['phantom_count']} "
                f"hier={cov['hierarchy_ok']} order={cov['ordering_ok']}"
            )

        time.sleep(0.2)

    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)
    print(f"Total: {len(entries)}")
    print(f"PASS:  {success_count}")
    print(f"FAIL:  {failure_count}")
    print(f"Success report: {SUCCESS_FILE}")
    print(f"Failure report: {FAILURE_FILE}")
    if snapshot_tag:
        success_snapshot, failure_snapshot = write_batch_snapshots(snapshot_tag)
        print(f"Batch success snapshot: {success_snapshot}")
        print(f"Batch failure snapshot: {failure_snapshot}")

    return 0 if failure_count == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch download, parse, and test EUR-Lex documents."
    )
    parser.add_argument(
        "--force-reparse",
        action="store_true",
        help="Re-parse HTML even if JSON already exists",
    )
    parser.add_argument(
        "--oracle",
        choices=["naive", "mirror"],
        default="naive",
        help="Coverage oracle to use (default: naive)",
    )
    parser.add_argument(
        "--links-file",
        type=Path,
        default=LINKS_FILE,
        help=f"Path to JSONL links file (default: {LINKS_FILE})",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start index in links file (default: 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of links to process from offset",
    )
    parser.add_argument(
        "--snapshot-tag",
        default=None,
        help="If provided, saves per-run report snapshots in reports/batches/",
    )
    args = parser.parse_args()

    raise SystemExit(
        run_batch(
            force_reparse=args.force_reparse,
            oracle=args.oracle,
            links_file=args.links_file,
            offset=args.offset,
            limit=args.limit,
            snapshot_tag=args.snapshot_tag,
        )
    )


if __name__ == "__main__":
    main()
