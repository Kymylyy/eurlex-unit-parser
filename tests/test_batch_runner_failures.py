"""Failure-path tests for batch runner orchestration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from eurlex_unit_parser.batch import runner


def _patch_batch_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.DOWNLOAD_DIR", tmp_path / "downloads")
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.JSON_DIR", tmp_path / "json")
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.SUCCESS_FILE",
        tmp_path / "reports" / "eurlex_coverage_success.jsonl",
    )
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.FAILURE_FILE",
        tmp_path / "reports" / "eurlex_coverage_failures.jsonl",
    )
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.BATCH_REPORTS_DIR",
        tmp_path / "reports" / "batches",
    )
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.time.sleep", lambda _: None)


def test_run_batch_returns_error_when_links_file_is_missing(monkeypatch, tmp_path: Path) -> None:
    _patch_batch_paths(monkeypatch, tmp_path)
    missing_links = tmp_path / "missing.jsonl"
    assert runner.run_batch(links_file=missing_links) == 1


def test_run_batch_returns_error_for_invalid_limit(monkeypatch, tmp_path: Path) -> None:
    _patch_batch_paths(monkeypatch, tmp_path)
    links_file = tmp_path / "links.jsonl"
    links_file.write_text('{"url":"https://eur-lex.europa.eu/1"}\n', encoding="utf-8")

    assert runner.run_batch(links_file=links_file, limit=0) == 1
    assert not (tmp_path / "reports" / "eurlex_coverage_success.jsonl").exists()
    assert not (tmp_path / "reports" / "eurlex_coverage_failures.jsonl").exists()


def test_run_batch_records_download_failures(monkeypatch, tmp_path: Path) -> None:
    _patch_batch_paths(monkeypatch, tmp_path)
    links_file = tmp_path / "links.jsonl"
    links_file.write_text('{"url":"https://eur-lex.europa.eu/42","celex":"32024R0042"}\n', encoding="utf-8")

    monkeypatch.setattr("eurlex_unit_parser.batch.runner.download_html", lambda *_: (False, "network_down"))
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.parse_html",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("parse_html should not be called")),
    )
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.run_coverage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("run_coverage should not be called")),
    )

    exit_code = runner.run_batch(force_reparse=True, links_file=links_file)
    assert exit_code == 1

    failure_lines = (tmp_path / "reports" / "eurlex_coverage_failures.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(failure_lines) == 1
    assert "download_failed: network_down" in json.loads(failure_lines[0])["notes"]


def test_run_batch_records_parse_failures(monkeypatch, tmp_path: Path) -> None:
    _patch_batch_paths(monkeypatch, tmp_path)
    links_file = tmp_path / "links.jsonl"
    links_file.write_text('{"url":"https://eur-lex.europa.eu/99","celex":"32024R0099"}\n', encoding="utf-8")

    def fake_download(_url: str, html_path: Path):
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text("<html>" + ("x" * 2000) + "</html>", encoding="utf-8")
        return True, "fake_download"

    monkeypatch.setattr("eurlex_unit_parser.batch.runner.download_html", fake_download)
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.parse_html", lambda *_args, **_kwargs: (False, "bad_json"))
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.run_coverage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("run_coverage should not be called")),
    )

    exit_code = runner.run_batch(force_reparse=True, links_file=links_file)
    assert exit_code == 1

    failure_lines = (tmp_path / "reports" / "eurlex_coverage_failures.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(failure_lines) == 1
    assert "parse_failed: bad_json" in json.loads(failure_lines[0])["notes"]


def test_run_coverage_returns_timeout_note(monkeypatch, tmp_path: Path) -> None:
    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="coverage", timeout=120)

    monkeypatch.setattr("eurlex_unit_parser.batch.runner.subprocess.run", raise_timeout)

    report = runner.run_coverage(tmp_path / "in.html", tmp_path / "out.json", oracle="naive")
    assert report["notes"] == "coverage_timeout"
    assert report["coverage_pct"] == 0.0
    assert report["gone"] == -1


def test_run_coverage_parses_metrics_json_output(monkeypatch, tmp_path: Path) -> None:
    payload = (
        'METRICS_JSON: {"coverage_pct": 88.8, "text_recall_pct": 92.2, "gone": 3, '
        '"misclassified": 1, "total_missing": 5, "phantom": 2, "hierarchy_ok": false, '
        '"ordering_ok": false}\n'
    )
    fake_result = SimpleNamespace(returncode=1, stdout=payload, stderr="")
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.subprocess.run", lambda *_args, **_kwargs: fake_result)

    report = runner.run_coverage(tmp_path / "in.html", tmp_path / "out.json", oracle="mirror")
    assert report["coverage_pct"] == 88.8
    assert report["text_recall_pct"] == 92.2
    assert report["gone"] == 3
    assert report["missing_count"] == 5
    assert report["phantom_count"] == 2
    assert report["hierarchy_ok"] is False
    assert report["ordering_ok"] is False
