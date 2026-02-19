"""Behavioral tests for parse CLI branches beyond --help smoke checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from eurlex_unit_parser.cli import parse as parse_cli
from eurlex_unit_parser.models import DocumentMetadata, Unit, ValidationReport


class _FakeParser:
    def __init__(self, source_file: str):
        self.source_file = source_file
        self.document_metadata = DocumentMetadata(title="REGULATION (EU) 2024/1", total_units=1)
        self.validation = ValidationReport(
            source_file=source_file,
            counts_parsed={"article": 1, "paragraph": 0},
        )

    def parse(self, _html: str) -> list[Unit]:
        return [
            Unit(
                id="art-1",
                type="article",
                ref="1",
                text="Article text.",
                parent_id=None,
                source_id="art_1",
                source_file=self.source_file,
                article_number="1",
            )
        ]


def test_main_returns_exit_1_for_missing_input(monkeypatch, tmp_path: Path) -> None:
    missing_html = tmp_path / "missing.html"
    monkeypatch.setattr(sys, "argv", ["eurlex-parse", "--input", str(missing_html)])

    with pytest.raises(SystemExit) as exc:
        parse_cli.main()

    assert exc.value.code == 1


def test_main_writes_json_and_default_validation_report(monkeypatch, tmp_path: Path) -> None:
    input_html = tmp_path / "sample.html"
    input_html.write_text("<html><body>ok</body></html>", encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(parse_cli, "EUParser", _FakeParser)
    monkeypatch.setattr(parse_cli, "fetch_lsu_summary", lambda **_kwargs: (None, "disabled"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["eurlex-parse", "--input", str(input_html), "--out-dir", str(out_dir)],
    )

    parse_cli.main()

    output_path = out_dir / "json" / "sample.json"
    validation_path = out_dir / "validation" / "sample_validation.json"
    assert output_path.exists()
    assert validation_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["document_metadata"]["title"] == "REGULATION (EU) 2024/1"
    assert payload["summary_lsu"] is None
    assert payload["summary_lsu_status"] == "disabled"
    assert len(payload["units"]) == 1


def test_main_exits_1_when_coverage_flag_reports_failure(monkeypatch, tmp_path: Path) -> None:
    input_html = tmp_path / "sample.html"
    input_html.write_text("<html><body>ok</body></html>", encoding="utf-8")
    out_path = tmp_path / "out.json"
    monkeypatch.setattr(parse_cli, "EUParser", _FakeParser)
    monkeypatch.setattr(parse_cli, "fetch_lsu_summary", lambda **_kwargs: (None, "disabled"))

    import eurlex_unit_parser.coverage as coverage_mod

    monkeypatch.setattr(coverage_mod, "coverage_test", lambda *_args, **_kwargs: {"summary": {}})
    monkeypatch.setattr(coverage_mod, "validate_hierarchy", lambda *_args, **_kwargs: {"valid": True, "issues": []})
    monkeypatch.setattr(coverage_mod, "print_report", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["eurlex-parse", "--input", str(input_html), "--out", str(out_path), "--coverage"],
    )

    with pytest.raises(SystemExit) as exc:
        parse_cli.main()

    assert exc.value.code == 1


def test_main_no_summary_lsu_sets_disabled_without_fetch(monkeypatch, tmp_path: Path) -> None:
    input_html = tmp_path / "sample.html"
    input_html.write_text("<html><body>ok</body></html>", encoding="utf-8")
    out_path = tmp_path / "out.json"
    monkeypatch.setattr(parse_cli, "EUParser", _FakeParser)
    monkeypatch.setattr(
        parse_cli,
        "fetch_lsu_summary",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("fetch_lsu_summary should not be called")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["eurlex-parse", "--input", str(input_html), "--out", str(out_path), "--no-summary-lsu"],
    )

    parse_cli.main()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary_lsu"] is None
    assert payload["summary_lsu_status"] == "disabled"
