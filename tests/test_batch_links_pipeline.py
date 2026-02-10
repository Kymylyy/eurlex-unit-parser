"""Tests for links slicing and CSV->JSONL conversion helpers."""

from __future__ import annotations

import json
from pathlib import Path

from eurlex_unit_parser.batch.links_convert import convert_csv_to_jsonl, csv_row_to_jsonl_entry
from eurlex_unit_parser.batch.runner import load_entries, run_batch, slice_entries


def test_slice_entries_offset_and_limit() -> None:
    entries = [{"url": f"https://example.com/{i}"} for i in range(5)]
    assert slice_entries(entries, offset=0, limit=2) == entries[:2]
    assert slice_entries(entries, offset=2, limit=2) == entries[2:4]
    assert slice_entries(entries, offset=3, limit=None) == entries[3:]


def test_slice_entries_invalid_values_raise() -> None:
    entries = [{"url": "https://example.com/1"}]
    try:
        slice_entries(entries, offset=-1, limit=None)
    except ValueError as exc:
        assert "offset" in str(exc)
    else:
        raise AssertionError("Expected ValueError for offset < 0")

    try:
        slice_entries(entries, offset=0, limit=0)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("Expected ValueError for limit <= 0")


def test_csv_row_to_jsonl_entry_maps_category_hint() -> None:
    row = {
        "url": " https://eur-lex.europa.eu/example ",
        "celex": " 32024R1689 ",
        "title": " AI Act ",
        "category": " ai_tech ",
    }
    entry = csv_row_to_jsonl_entry(row)
    assert entry == {
        "url": "https://eur-lex.europa.eu/example",
        "celex": "32024R1689",
        "title": "AI Act",
        "category_hint": "ai_tech",
        "source": "candidate_csv",
    }


def test_convert_csv_to_jsonl_and_load_entries(tmp_path: Path) -> None:
    csv_path = tmp_path / "links.csv"
    csv_path.write_text(
        "url,celex,title,category\n"
        "https://eur-lex.europa.eu/a,32024R1689,AI Act,ai_tech\n"
        "https://eur-lex.europa.eu/b,32023R2854,Data Act,ai_tech\n",
        encoding="utf-8",
    )
    jsonl_path = tmp_path / "links.jsonl"

    count = convert_csv_to_jsonl(csv_path, jsonl_path)
    assert count == 2
    assert jsonl_path.exists()

    entries = load_entries(jsonl_path)
    assert [entry["celex"] for entry in entries] == ["32024R1689", "32023R2854"]
    assert all(entry["source"] == "candidate_csv" for entry in entries)


def test_run_batch_uses_links_file_offset_and_limit(monkeypatch, tmp_path: Path) -> None:
    links_file = tmp_path / "links.jsonl"
    raw_entries = [
        {"url": f"https://eur-lex.europa.eu/{i}", "celex": f"32000R00{i:02d}"}
        for i in range(3)
    ]
    links_file.write_text("\n".join(json.dumps(entry) for entry in raw_entries) + "\n", encoding="utf-8")

    called_urls: list[str] = []

    def fake_download(url: str, html_path: Path):
        called_urls.append(url)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text("<html><body>ok</body></html>", encoding="utf-8")
        return True, "fake"

    def fake_parse(html_path: Path, json_path: Path, force: bool = False):
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text('{"document_metadata":{},"units":[]}', encoding="utf-8")
        return True, "ok"

    def fake_coverage(html_path: Path, json_path: Path, oracle: str = "naive"):
        return {
            "coverage_pct": 100.0,
            "missing_count": 0,
            "phantom_count": 0,
            "gone": 0,
            "misclassified": 0,
            "text_recall_pct": 100.0,
            "hierarchy_ok": True,
            "ordering_ok": True,
            "notes": "ok",
        }

    monkeypatch.setattr("eurlex_unit_parser.batch.runner.DOWNLOAD_DIR", tmp_path / "downloads")
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.JSON_DIR", tmp_path / "json")
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.REPORTS_DIR", tmp_path / "reports"
    )
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.SUCCESS_FILE",
        tmp_path / "reports" / "eurlex_coverage_success.jsonl",
    )
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.FAILURE_FILE",
        tmp_path / "reports" / "eurlex_coverage_failures.jsonl",
    )
    monkeypatch.setattr(
        "eurlex_unit_parser.batch.runner.BATCH_REPORTS_DIR", tmp_path / "reports" / "batches"
    )
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.download_html", fake_download)
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.parse_html", fake_parse)
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.run_coverage", fake_coverage)
    monkeypatch.setattr("eurlex_unit_parser.batch.runner.time.sleep", lambda _: None)

    exit_code = run_batch(
        force_reparse=True,
        oracle="mirror",
        links_file=links_file,
        offset=1,
        limit=1,
        snapshot_tag="batch_01",
    )
    assert exit_code == 0
    assert called_urls == ["https://eur-lex.europa.eu/1"]

    success_snapshot = tmp_path / "reports" / "batches" / "batch_01_success.jsonl"
    failure_snapshot = tmp_path / "reports" / "batches" / "batch_01_failures.jsonl"
    assert success_snapshot.exists()
    assert failure_snapshot.exists()
