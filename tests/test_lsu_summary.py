"""Tests for LSU summary fetch and parsing helpers."""

from __future__ import annotations

import requests

from eurlex_unit_parser.summary.lsu import (
    LSU_STATUS_CELEX_MISSING,
    LSU_STATUS_FETCH_ERROR,
    LSU_STATUS_NOT_FOUND,
    LSU_STATUS_OK,
    fetch_lsu_summary,
)


class _FakeResponse:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url


def _source_html(celex: str = "32022R2554", lang: str = "en") -> str:
    return (
        "<html><head>"
        f'<meta name="WT.z_docID" content="{celex}">'
        f'<meta name="WT.z_usr_lan" content="{lang}">'
        "</head><body></body></html>"
    )


def _lsu_html() -> str:
    return (
        "<html><head>"
        '<link rel="canonical" href="https://eur-lex.europa.eu/EN/legal-content/summary/example.html">'
        "</head><body>"
        "<h1>Digital operational resilience for the financial sector</h1>"
        '<section id="lseu-section-summary-of">'
        "<h2>SUMMARY OF:</h2>"
        "<p>Regulation (EU) 2022/2554</p>"
        "</section>"
        '<section id="lseu-section-key-points">'
        "<h2>KEY POINTS</h2>"
        "<p>It covers:</p>"
        "<ul><li>banks</li><li>insurers</li></ul>"
        "</section>"
        '<p class="lseu-lastmod">last update <time datetime="2026-01-26">26.1.2026</time></p>'
        "</body></html>"
    )


def _missing_html() -> str:
    return (
        "<html><body>"
        '<div class="alert alert-warning">The requested document does not exist.</div>'
        "</body></html>"
    )


def test_fetch_lsu_summary_returns_parsed_payload(monkeypatch) -> None:
    called_urls: list[str] = []

    def fake_get(url: str, **_kwargs):
        called_urls.append(url)
        return _FakeResponse(_lsu_html(), url)

    monkeypatch.setattr("eurlex_unit_parser.summary.lsu.requests.get", fake_get)

    summary, status = fetch_lsu_summary(
        html_content=_source_html(),
        source_file="downloads/eur-lex/32022R2554.html",
    )

    assert status == LSU_STATUS_OK
    assert summary is not None
    assert summary.celex == "32022R2554"
    assert summary.language == "EN"
    assert summary.title == "Digital operational resilience for the financial sector"
    assert summary.last_modified_date == "2026-01-26"
    assert summary.canonical_url == "https://eur-lex.europa.eu/EN/legal-content/summary/example.html"
    assert summary.sections[0].heading == "SUMMARY OF:"
    assert "Regulation (EU) 2022/2554" in summary.sections[0].content
    assert "- banks" in summary.sections[1].content
    assert called_urls and "/EN/LSU/" in called_urls[0]


def test_fetch_lsu_summary_returns_not_found_for_missing_page(monkeypatch) -> None:
    monkeypatch.setattr(
        "eurlex_unit_parser.summary.lsu.requests.get",
        lambda url, **_kwargs: _FakeResponse(_missing_html(), url),
    )

    summary, status = fetch_lsu_summary(
        html_content=_source_html(celex="32024R9999"),
        source_file="downloads/eur-lex/32024R9999.html",
    )

    assert summary is None
    assert status == LSU_STATUS_NOT_FOUND


def test_fetch_lsu_summary_returns_fetch_error_on_network_failure(monkeypatch) -> None:
    def raise_error(*_args, **_kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr("eurlex_unit_parser.summary.lsu.requests.get", raise_error)

    summary, status = fetch_lsu_summary(
        html_content=_source_html(celex="32022R2554"),
        source_file="downloads/eur-lex/32022R2554.html",
    )

    assert summary is None
    assert status == LSU_STATUS_FETCH_ERROR


def test_fetch_lsu_summary_returns_celex_missing_without_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        "eurlex_unit_parser.summary.lsu.requests.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("requests.get should not be called")),
    )

    summary, status = fetch_lsu_summary(
        html_content="<html><head></head><body></body></html>",
        source_file="downloads/eur-lex/DORA.html",
    )

    assert summary is None
    assert status == LSU_STATUS_CELEX_MISSING


def test_fetch_lsu_summary_falls_back_from_consolidated_to_base_celex(monkeypatch) -> None:
    called_urls: list[str] = []

    def fake_get(url: str, **_kwargs):
        called_urls.append(url)
        if "CELEX:02016R0679-20160504" in url:
            return _FakeResponse(_missing_html(), url)
        if "CELEX:32016R0679" in url:
            return _FakeResponse(_lsu_html(), url)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("eurlex_unit_parser.summary.lsu.requests.get", fake_get)

    summary, status = fetch_lsu_summary(
        celex="02016R0679-20160504",
        language="EN",
    )

    assert status == LSU_STATUS_OK
    assert summary is not None
    assert summary.celex == "32016R0679"
    assert len(called_urls) == 2
