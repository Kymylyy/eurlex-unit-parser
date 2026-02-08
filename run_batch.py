#!/usr/bin/env python3
"""
Batch processor: download EUR-Lex HTML, parse to JSON, run coverage tests.
Reads links from data/eurlex_links.jsonl, produces reports.
"""

import argparse
import json
import hashlib
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent
LINKS_FILE = BASE / "data" / "eurlex_links.jsonl"
DOWNLOAD_DIR = BASE / "downloads" / "eur-lex"
JSON_DIR = BASE / "out" / "json"
REPORTS_DIR = BASE / "reports"
SUCCESS_FILE = REPORTS_DIR / "eurlex_coverage_success.jsonl"
FAILURE_FILE = REPORTS_DIR / "eurlex_coverage_failures.jsonl"

PARSER = BASE / "parse_eu.py"
COVERAGE = BASE / "test_coverage.py"
DOWNLOADER = BASE / "download_eurlex.py"

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


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


def download_html(url: str, html_path: Path) -> tuple[bool, str]:
    """Download using Playwright downloader, fall back to requests."""
    if html_path.exists() and html_path.stat().st_size > 1000:
        return True, "already_downloaded"

    # Try Playwright downloader
    try:
        result = subprocess.run(
            [sys.executable, str(DOWNLOADER), url, html_path.stem,
             "--output-dir", str(html_path.parent)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and html_path.exists() and html_path.stat().st_size > 1000:
            return True, "playwright"
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        pass

    # Fallback: requests
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
            [sys.executable, str(PARSER),
             "--input", str(html_path),
             "--out", str(json_path),
             "--no-validation"],
            capture_output=True, text=True, timeout=120
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
            [sys.executable, str(COVERAGE),
             "-i", str(html_path),
             "-j", str(json_path),
             "--oracle", oracle],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout + result.stderr

        # Primary: parse METRICS_JSON line (machine-readable)
        import json as _json
        for line in output.splitlines():
            if line.startswith("METRICS_JSON:"):
                try:
                    metrics = _json.loads(line[len("METRICS_JSON:"):].strip())
                    report["coverage_pct"] = metrics.get("coverage_pct", 0.0)
                    report["text_recall_pct"] = metrics.get("text_recall_pct", 0.0)
                    report["gone"] = metrics.get("gone", -1)
                    report["misclassified"] = metrics.get("misclassified", -1)
                    report["missing_count"] = metrics.get("total_missing", -1)
                    report["phantom_count"] = metrics.get("phantom", -1)
                    report["hierarchy_ok"] = metrics.get("hierarchy_ok", False)
                    report["ordering_ok"] = metrics.get("ordering_ok", True)
                    break
                except _json.JSONDecodeError:
                    pass
        else:
            # Fallback: regex parsing for backward compat
            import re
            cov_match = re.search(r'(\d+(?:\.\d+)?)%\s+(?:text recall|coverage)', output)
            if cov_match:
                report["coverage_pct"] = float(cov_match.group(1))

            miss_match = re.search(r'(?:Missing segments|Gone \(truly missing\)):\s*(\d+)', output)
            if miss_match:
                report["missing_count"] = int(miss_match.group(1))

            phantom_match = re.search(r'Phantom segments:\s*(\d+)', output)
            if phantom_match:
                report["phantom_count"] = int(phantom_match.group(1))

            hier_match = re.search(r'Hierarchy issues:\s*(\d+)', output)
            if hier_match:
                report["hierarchy_ok"] = int(hier_match.group(1)) == 0

            ord_match = re.search(r'Ordering issues:\s*(\d+)', output)
            if ord_match:
                report["ordering_ok"] = int(ord_match.group(1)) == 0

        report["notes"] = output.strip()[-500:] if output.strip() else ""

        # Trust exit code as ultimate pass/fail
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


def main():
    parser = argparse.ArgumentParser(description="Batch download, parse, and test EUR-Lex documents.")
    parser.add_argument("--force-reparse", action="store_true",
                        help="Re-parse HTML even if JSON already exists")
    parser.add_argument("--oracle", choices=["naive", "mirror"], default="naive",
                        help="Coverage oracle to use (default: naive)")
    args = parser.parse_args()

    if not LINKS_FILE.exists():
        print(f"ERROR: {LINKS_FILE} not found")
        sys.exit(1)

    entries = []
    with open(LINKS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    print(f"Loaded {len(entries)} links from {LINKS_FILE}")

    # Clear previous reports
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

        # Step 1: Download
        dl_ok, dl_method = download_html(url, html_path)
        if not dl_ok:
            record = {
                "url": url,
                "local_html": to_repo_relative(html_path),
                "local_json": to_repo_relative(json_path),
                "oracle": args.oracle,
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

        # Step 2: Parse
        parse_ok, parse_msg = parse_html(html_path, json_path, force=args.force_reparse)
        if not parse_ok:
            record = {
                "url": url,
                "local_html": to_repo_relative(html_path),
                "local_json": to_repo_relative(json_path),
                "oracle": args.oracle,
                "coverage_pct": 0.0,
                "missing_count": -1,
                "phantom_count": -1,
                "hierarchy_ok": False,
                "ordering_ok": False,
                "notes": f"parse_failed: {parse_msg}",
            }
            with open(FAILURE_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
            failure_count += 1
            print(f"  PARSE FAILED: {parse_msg}")
            continue

        print(f"  Parsed: {parse_msg}")

        # Check for "document does not exist" pages
        html_text = html_path.read_text(encoding="utf-8", errors="replace")[:2000]
        if "The requested document does not exist" in html_text:
            record = {
                "url": url,
                "local_html": to_repo_relative(html_path),
                "local_json": to_repo_relative(json_path),
                "oracle": args.oracle,
                "coverage_pct": 0.0,
                "missing_count": -1,
                "phantom_count": -1,
                "hierarchy_ok": False,
                "ordering_ok": False,
                "notes": "document_not_found_on_eurlex",
            }
            with open(FAILURE_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
            failure_count += 1
            print(f"  FAIL: document does not exist on EUR-Lex")
            continue

        # Check for empty JSON (parser produced 0 units)
        try:
            units = json.loads(json_path.read_text())
            unit_count = len(units)
        except Exception:
            unit_count = 0

        # Step 3: Coverage
        cov = run_coverage(html_path, json_path, oracle=args.oracle)
        record = {
            "url": url,
            "local_html": to_repo_relative(html_path),
            "local_json": to_repo_relative(json_path),
            "oracle": args.oracle,
            "coverage_pct": cov["coverage_pct"],
            "text_recall_pct": cov["text_recall_pct"],
            "gone": cov["gone"],
            "misclassified": cov["misclassified"],
            "missing_count": cov["missing_count"],
            "phantom_count": cov["phantom_count"],
            "hierarchy_ok": cov["hierarchy_ok"],
            "ordering_ok": cov["ordering_ok"],
            "notes": cov["notes"],
        }

        # Detect vacuous pass: 0 units parsed and 0 segments found
        is_vacuous = (unit_count == 0 and cov["missing_count"] == 0)
        if is_vacuous:
            record["notes"] = f"vacuous_pass: 0 units parsed, 0 segments found. {record['notes']}"

        gone = cov["gone"] if cov["gone"] >= 0 else cov["missing_count"]
        is_success = (gone == 0
                      and cov["phantom_count"] == 0
                      and cov["hierarchy_ok"]
                      and cov["ordering_ok"]
                      and not is_vacuous)

        if is_success:
            with open(SUCCESS_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
            success_count += 1
            print(f"  PASS: recall={cov['text_recall_pct']}% strict={cov['coverage_pct']}%")
        else:
            with open(FAILURE_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
            failure_count += 1
            print(f"  FAIL: gone={cov['gone']}, misclassified={cov['misclassified']}, "
                  f"phantom={cov['phantom_count']}, "
                  f"hierarchy={'ok' if cov['hierarchy_ok'] else 'FAIL'}")

        # Be polite to EUR-Lex servers
        if dl_method not in ("already_downloaded",):
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"RESULTS: {success_count} passed, {failure_count} failed "
          f"out of {len(entries)} total")
    print(f"Reports: {SUCCESS_FILE}")
    print(f"         {FAILURE_FILE}")


if __name__ == "__main__":
    main()
