"""Regression tests for amending article parsing on the hardest CELEX documents."""
from dataclasses import asdict
import json
import tempfile
from pathlib import Path

import pytest

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_eu import EUParser
from test_coverage import (
    coverage_test, validate_hierarchy, validate_ordering,
    build_full_html_text_by_section, build_json_section_texts,
)
from bs4 import BeautifulSoup

HTML_DIR = Path(__file__).parent.parent / "downloads" / "eur-lex"

AMENDING_CELEX = [
    "32019R0876",   # CRR2 — Capital Requirements Regulation II
    "32019L0878",   # CRD V — Capital Requirements Directive V
    "32022L2464",   # CSRD — Corporate Sustainability Reporting Directive
]


def _parse_and_test(celex: str):
    """Parse HTML and run coverage test, returning metrics dict."""
    html_path = HTML_DIR / f"{celex}.html"
    if not html_path.exists():
        pytest.skip(f"HTML not found: {html_path}")

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    parser = EUParser(str(html_path))
    units = parser.parse(html_content)
    units_data = [asdict(u) for u in units]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "document_metadata": asdict(parser.document_metadata) if parser.document_metadata else None,
                "units": units_data,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
        json_path = Path(f.name)

    try:
        report = coverage_test(html_path, json_path, oracle="mirror")

        with open(json_path) as f:
            payload = json.load(f)
            units_data = payload["units"]

        hierarchy = validate_hierarchy(units_data)
        ordering = validate_ordering(units_data)

        # Phantom check
        with open(html_path) as f:
            soup = BeautifulSoup(f.read(), "lxml")
        full_html = build_full_html_text_by_section(soup)
        json_sections = build_json_section_texts(units_data)
        phantom_count = 0
        for key, texts in json_sections.items():
            html_text = full_html.get(key, "")
            for t in texts:
                if t and t not in html_text:
                    phantom_count += 1

        return {
            "gone": report["summary"].get("gone", report["summary"]["total_missing"]),
            "misclassified": report["summary"].get("misclassified", 0),
            "coverage_pct": report["summary"]["coverage_pct"],
            "text_recall_pct": report["summary"].get("text_recall_pct", report["summary"]["coverage_pct"]),
            "phantom": phantom_count,
            "hierarchy_ok": hierarchy["valid"],
            "hierarchy_issues": len(hierarchy["issues"]),
            "ordering_ok": ordering["valid"],
            "total_html": report["summary"]["total_html_segments"],
            "total_units": len(units_data),
        }
    finally:
        json_path.unlink(missing_ok=True)


@pytest.mark.parametrize("celex", AMENDING_CELEX)
def test_no_text_loss(celex):
    """Hard requirement: no text truly missing from JSON (gone == 0)."""
    metrics = _parse_and_test(celex)
    assert metrics["gone"] == 0, (
        f"{celex}: {metrics['gone']} segments truly missing from JSON "
        f"(text recall: {metrics['text_recall_pct']:.1f}%)"
    )


@pytest.mark.parametrize("celex", AMENDING_CELEX)
def test_no_phantoms(celex):
    """No hallucinated text in JSON that doesn't exist in HTML."""
    metrics = _parse_and_test(celex)
    assert metrics["phantom"] == 0, (
        f"{celex}: {metrics['phantom']} phantom segments in JSON"
    )


@pytest.mark.parametrize("celex", AMENDING_CELEX)
def test_hierarchy_valid(celex):
    """All parent_ids must be valid and type rules satisfied."""
    metrics = _parse_and_test(celex)
    assert metrics["hierarchy_ok"], (
        f"{celex}: {metrics['hierarchy_issues']} hierarchy issues"
    )


@pytest.mark.parametrize("celex", AMENDING_CELEX)
def test_ordering_valid(celex):
    """No interleaved point/subparagraph sequences."""
    metrics = _parse_and_test(celex)
    assert metrics["ordering_ok"], f"{celex}: ordering issues detected"


@pytest.mark.parametrize("celex", AMENDING_CELEX)
def test_type_accuracy_report(celex):
    """Informational: report misclassification count (not gating)."""
    metrics = _parse_and_test(celex)
    print(f"\n{celex}: misclassified={metrics['misclassified']}, "
          f"strict={metrics['coverage_pct']:.1f}%, "
          f"recall={metrics['text_recall_pct']:.1f}%, "
          f"units={metrics['total_units']}")


def test_dora_footnote_citation_not_parsed_as_amendment_text():
    """Footnote OJ citations in DORA amendments must not become JSON units."""
    html_path = HTML_DIR / "DORA.html"
    if not html_path.exists():
        pytest.skip(f"HTML not found: {html_path}")

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    parser = EUParser(str(html_path))
    units = parser.parse(html_content)
    units_data = [asdict(u) for u in units]

    soup = BeautifulSoup(html_content, "lxml")
    html_footnotes = 0
    for art_id in ("art_59", "art_60", "art_61", "art_62"):
        art = soup.find("div", id=art_id)
        if not art:
            continue
        for p in art.find_all("p", class_="oj-note"):
            if "OJ L 333, 27.12.2022, p. 1" in p.get_text(" ", strip=True):
                html_footnotes += 1

    assert html_footnotes >= 4, "Expected OJ footnote citations in DORA HTML"

    leaked = [
        u["id"] for u in units_data
        if u.get("article_number") in {"59", "60", "61", "62"}
        and "OJ L 333, 27.12.2022, p. 1" in u.get("text", "")
    ]
    assert leaked == [], f"Footnote citation leaked into JSON units: {leaked}"
