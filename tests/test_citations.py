"""Unit tests for citation extraction enrichment."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_eu import EUParser, Unit


def _make_unit(id: str, type: str, text: str = "", parent_id: str | None = None, **kwargs) -> Unit:
    return Unit(
        id=id,
        type=type,
        ref=None,
        text=text,
        parent_id=parent_id,
        source_id="",
        source_file="inline.html",
        **kwargs,
    )


def _run_enrichment(units: list[Unit]) -> EUParser:
    parser = EUParser("inline.html")
    parser.units = units
    parser._enrich()
    return parser


def test_internal_simple_article_paragraph() -> None:
    units = [_make_unit("u1", "paragraph", text="as referred to in Article 6(1).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 6
    assert citations[0].paragraph == 1
    assert citations[0].target_node_id == "art-6.par-1"


def test_internal_article_first_point() -> None:
    units = [_make_unit("u1", "paragraph", text="See Article 2(1), point (b).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 2
    assert citations[0].paragraph == 1
    assert citations[0].point == "b"
    assert citations[0].target_node_id == "art-2.par-1.pt-b"


def test_internal_point_first() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in point (b) of Article 2(1).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 2
    assert citations[0].paragraph == 1
    assert citations[0].point == "b"
    assert citations[0].target_node_id == "art-2.par-1.pt-b"


def test_external_standalone() -> None:
    units = [_make_unit("u1", "paragraph", text="in accordance with Regulation (EU) 2016/679.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].act_type == "regulation"
    assert citations[0].act_number == "2016/679"
    assert citations[0].celex == "32016R0679"


def test_external_with_article() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text="under Article 6(1)(c) of Regulation (EU) 2016/679.",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].article == 6
    assert citations[0].paragraph == 1
    assert citations[0].point == "c"
    assert citations[0].target_node_id == "art-6.par-1.pt-c"
    assert citations[0].celex == "32016R0679"


def test_external_old_directive_format() -> None:
    units = [_make_unit("u1", "paragraph", text="as required by Directive 95/46/EC.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].act_type == "directive"
    assert citations[0].act_number == "95/46"
    assert citations[0].celex == "31995L0046"


def test_external_old_regulation_no_format() -> None:
    units = [_make_unit("u1", "paragraph", text="pursuant to Regulation (EC) No 45/2001.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].act_type == "regulation"
    assert citations[0].act_number == "45/2001"
    assert citations[0].celex == "32001R0045"


def test_overlap_prevention_external_with_article() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text="in accordance with Article 6(1) of Regulation (EU) 2016/679.",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].raw_text == "Article 6(1) of Regulation (EU) 2016/679"


def test_relative_reference_this_regulation() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in this Regulation.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].raw_text == "this Regulation"


def test_amendment_units_are_skipped() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text="Article 6(1) of Regulation (EU) 2016/679",
            is_amendment_text=True,
        )
    ]
    _run_enrichment(units)

    assert units[0].citations == []


def test_multiple_citations_in_single_unit() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text="in accordance with Article 5(2) and Regulation (EU) 2016/679.",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 5
    assert citations[0].paragraph == 2
    assert citations[1].citation_type == "eu_legislation"
    assert citations[1].celex == "32016R0679"


def test_old_article_spacing() -> None:
    units = [_make_unit("u1", "paragraph", text="as provided in Article 3 (1).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 3
    assert citations[0].paragraph == 1


def test_article_range() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in Articles 5 to 15.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article_range == (5, 15)
    assert citations[0].target_node_id is None


def test_paragraph_reference() -> None:
    units = [_make_unit("u1", "paragraph", text="as referred to in paragraph 3.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].paragraph == 3
    assert citations[0].target_node_id == "par-3"
