"""Tests for high-level library API helpers and parser stateless behavior."""

from __future__ import annotations

from pathlib import Path

from eurlex_unit_parser.api import JobResult, ParseResult, download_and_parse, parse_file, parse_html
from eurlex_unit_parser.download.eurlex import DownloadResult
from eurlex_unit_parser.parser.engine import EUParser


def _simple_html(article_id: str = "1") -> str:
    return (
        "<html><body>"
        f'<div class="eli-subdivision" id="art_{article_id}">'
        f"<p class=\"oj-ti-art\">Article {article_id}</p>"
        "<div id=\"001.001\"><p class=\"oj-normal\">1. Text.</p></div>"
        "</div>"
        "</body></html>"
    )


def test_parser_parse_resets_runtime_state_between_calls() -> None:
    parser = EUParser("inline.html")

    first = parser.parse(_simple_html("1"))
    second = parser.parse(_simple_html("1"))

    assert len(first) == len(second) == 2
    assert [unit.id for unit in first] == [unit.id for unit in second]
    assert parser.validation.counts_parsed == {"article": 1, "paragraph": 1}


def test_parse_html_returns_parse_result() -> None:
    result = parse_html(_simple_html("7"), source_file="inline.html", with_summary_lsu=False)

    assert isinstance(result, ParseResult)
    assert result.source_file == "inline.html"
    assert len(result.units) == 2
    assert result.summary_lsu is None
    assert result.summary_lsu_status == "disabled"
    assert result.validation.counts_parsed == {"article": 1, "paragraph": 1}


def test_parse_file_reads_file_and_parses(tmp_path: Path) -> None:
    path = tmp_path / "sample.html"
    path.write_text(_simple_html("2"), encoding="utf-8")

    result = parse_file(path, with_summary_lsu=False)

    assert isinstance(result, ParseResult)
    assert result.source_file == str(path)
    assert len(result.units) == 2
    assert result.summary_lsu is None
    assert result.summary_lsu_status == "disabled"
    assert result.validation.counts_parsed == {"article": 1, "paragraph": 1}


def test_download_and_parse_returns_parse_result_on_success(monkeypatch, tmp_path: Path) -> None:
    html_path = tmp_path / "downloaded.html"
    html_path.write_text(_simple_html("3"), encoding="utf-8")
    download_result = DownloadResult(
        ok=True,
        status="ok",
        error=None,
        output_path=html_path,
        final_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        bytes_written=html_path.stat().st_size,
        method="playwright",
    )
    monkeypatch.setattr("eurlex_unit_parser.api.download_eurlex", lambda *_args, **_kwargs: download_result)
    monkeypatch.setattr("eurlex_unit_parser.api.fetch_lsu_summary", lambda **_kwargs: (None, "ok"))

    job = download_and_parse(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        html_path,
        lang="EN",
    )

    assert isinstance(job, JobResult)
    assert job.download.ok is True
    assert job.parse is not None
    assert job.parse_error is None
    assert job.parse.summary_lsu is None
    assert job.parse.summary_lsu_status == "ok"
    assert len(job.parse.units) == 2


def test_download_and_parse_returns_download_failure_without_parse(monkeypatch, tmp_path: Path) -> None:
    download_result = DownloadResult(
        ok=False,
        status="navigation_error",
        error="timeout",
        output_path=tmp_path / "missing.html",
        final_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        bytes_written=0,
        method="playwright",
    )
    monkeypatch.setattr("eurlex_unit_parser.api.download_eurlex", lambda *_args, **_kwargs: download_result)

    job = download_and_parse(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        tmp_path / "missing.html",
        lang="EN",
    )

    assert isinstance(job, JobResult)
    assert job.download.ok is False
    assert job.parse is None
    assert job.parse_error is None


def test_download_and_parse_returns_parse_error_on_unreadable_file(monkeypatch, tmp_path: Path) -> None:
    download_result = DownloadResult(
        ok=True,
        status="ok",
        error=None,
        output_path=tmp_path / "not_written.html",
        final_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        bytes_written=128,
        method="playwright",
    )
    monkeypatch.setattr("eurlex_unit_parser.api.download_eurlex", lambda *_args, **_kwargs: download_result)

    job = download_and_parse(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        tmp_path / "not_written.html",
        lang="EN",
    )

    assert job.download.ok is True
    assert job.parse is None
    assert job.parse_error is not None


def test_parse_html_fetches_lsu_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "eurlex_unit_parser.api.fetch_lsu_summary",
        lambda **_kwargs: (None, "not_found"),
    )

    result = parse_html(_simple_html("8"), source_file="inline.html")

    assert result.summary_lsu is None
    assert result.summary_lsu_status == "not_found"
