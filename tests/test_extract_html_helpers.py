"""Targeted tests for extract_html helper branches with low current coverage."""

from __future__ import annotations

from bs4 import BeautifulSoup

from eurlex_unit_parser.coverage.extract_html import (
    build_naive_section_map,
    detect_format,
    looks_like_label,
    strip_leading_ref,
)


def test_strip_leading_ref_removes_nested_prefixes() -> None:
    assert strip_leading_ref("1. (a) — Actual legal text") == "Actual legal text"


def test_looks_like_label_detects_article_heading() -> None:
    assert looks_like_label("Article 8") is True
    assert looks_like_label("Substantive requirement text") is False


def test_build_naive_section_map_skips_correlation_table_annex() -> None:
    html = """
    <html><body>
      <div class="eli-container" id="anx_I">
        <p class="oj-doc-ti">ANNEX I</p>
        <p class="oj-ti-tbl">Correlation table</p>
        <p>Should be skipped entirely</p>
      </div>
      <div class="eli-container" id="anx_II">
        <p class="oj-doc-ti">ANNEX II</p>
        <p>Actual annex text retained for naive oracle.</p>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    sections = build_naive_section_map(soup)
    assert "annex_I" not in sections
    assert sections["annex_II"] == ["Actual annex text retained for naive oracle."]


def test_detect_format_true_when_grid_container_present() -> None:
    soup = BeautifulSoup("<html><body><div class='grid-container'></div></body></html>", "lxml")
    assert detect_format(soup) is True
