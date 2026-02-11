"""Unit tests for context-based citation resolver enrichment."""

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


def test_context_resolver_paragraph_of_this_article() -> None:
    units = [
        _make_unit(
            "art-5.par-2",
            "paragraph",
            article_number="5",
            paragraph_number="2",
            text="criteria referred to in paragraph 1 of this Article",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].article == 5
    assert citations[0].article_label == "5"
    assert citations[0].paragraph == 1
    assert citations[0].target_node_id == "art-5.par-1"


def test_context_resolver_this_article() -> None:
    units = [_make_unit("art-5", "article", article_number="5", text="as set out in this Article")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].raw_text == "this Article"
    assert citations[0].article == 5
    assert citations[0].article_label == "5"
    assert citations[0].target_node_id == "art-5"


def test_context_resolver_this_paragraph_from_paragraph_index() -> None:
    units = [
        _make_unit(
            "art-5.par-2",
            "paragraph",
            article_number="5",
            paragraph_index=2,
            text="as set out in this paragraph",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].raw_text == "this paragraph"
    assert citations[0].article == 5
    assert citations[0].article_label == "5"
    assert citations[0].paragraph == 2
    assert citations[0].target_node_id == "art-5.par-2"


def test_context_resolver_first_subparagraph_uses_eu_shift() -> None:
    units = [
        _make_unit(
            "art-5.par-2.subpar-1",
            "subparagraph",
            article_number="5",
            paragraph_number="2",
            subparagraph_index=1,
            text="as set out in the first subparagraph",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].article == 5
    assert citations[0].article_label == "5"
    assert citations[0].paragraph == 2
    assert citations[0].subparagraph_ordinal == "first"
    assert citations[0].target_node_id == "art-5.par-2"


def test_context_resolver_handles_alphanumeric_article_labels() -> None:
    units = [
        _make_unit(
            "art-6a.par-2",
            "paragraph",
            article_number="6a",
            paragraph_number="2",
            text="as set out in this paragraph",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].article == 6
    assert citations[0].article_label == "6a"
    assert citations[0].paragraph == 2
    assert citations[0].target_node_id == "art-6a.par-2"


def test_context_resolver_does_not_mutate_external_citations() -> None:
    units = [
        _make_unit(
            "art-5.par-2",
            "paragraph",
            article_number="5",
            paragraph_number="2",
            text="in accordance with Regulation (EU) 2016/679",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].article is None
    assert citations[0].paragraph is None
