"""Unit tests for context-based citation resolver enrichment."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_eu import Citation, EUParser, Unit


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


def _run_resolver_only(units: list[Unit]) -> EUParser:
    parser = EUParser("inline.html")
    parser.units = units
    parser._build_parent_index()
    parser._resolve_citations()
    return parser


def test_context_resolver_paragraph_of_this_article() -> None:
    units = [
        _make_unit("art-5.par-1", "paragraph", article_number="5", paragraph_number="1", text="Reference node."),
        _make_unit(
            "art-5.par-2",
            "paragraph",
            article_number="5",
            paragraph_number="2",
            text="criteria referred to in paragraph 1 of this Article",
        )
    ]
    _run_enrichment(units)

    citations = units[1].citations
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
        _make_unit("art-5.par-2", "paragraph", article_number="5", paragraph_number="2", text="Reference node."),
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

    citations = units[1].citations
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


def test_context_resolver_point_enumeration_uses_local_article_context() -> None:
    units = [
        _make_unit("art-5.par-2", "paragraph", article_number="5", paragraph_number="2", text="Reference node."),
        _make_unit("art-5.par-2.pt-a", "point", article_number="5", paragraph_number="2", point_label="a", text="A."),
        _make_unit("art-5.par-2.pt-b", "point", article_number="5", paragraph_number="2", point_label="b", text="B."),
        _make_unit(
            "art-5.par-2.intro-1",
            "intro",
            article_number="5",
            paragraph_number="2",
            text="points (a) and (b) apply.",
        ),
    ]
    _run_enrichment(units)

    citations = units[-1].citations
    assert len(citations) == 2
    assert {c.target_node_id for c in citations} == {"art-5.par-2.pt-a", "art-5.par-2.pt-b"}


def test_context_resolver_paragraph_enumeration_uses_local_article_context() -> None:
    units = [
        _make_unit("art-5.par-1", "paragraph", article_number="5", paragraph_number="1", text="P1."),
        _make_unit("art-5.par-2", "paragraph", article_number="5", paragraph_number="2", text="P2."),
        _make_unit("art-5.par-3", "paragraph", article_number="5", paragraph_number="3", text="P3."),
        _make_unit(
            "art-5.par-4",
            "paragraph",
            article_number="5",
            paragraph_number="4",
            text="paragraphs 1, 2 or 3 apply.",
        ),
    ]
    _run_enrichment(units)

    citations = units[-1].citations
    assert len(citations) == 3
    assert {c.target_node_id for c in citations} == {"art-5.par-1", "art-5.par-2", "art-5.par-3"}


def test_context_resolver_point_without_context_gets_null_target() -> None:
    units = [
        _make_unit("u1", "paragraph", text="points (a), (b) and (c) apply."),
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 3
    assert {citation.point for citation in citations} == {"a", "b", "c"}
    assert {citation.target_node_id for citation in citations} == {None}


def test_context_resolver_annex_part_uses_local_annex_context() -> None:
    units = [
        _make_unit("annex-I", "annex", annex_number="I", text="ANNEX I"),
        _make_unit("annex-I.part-A", "annex_part", annex_number="I", annex_part="A", text="PART A"),
        _make_unit(
            "annex-I.item-1",
            "annex_item",
            annex_number="I",
            text="as provided in Part A.",
            citations=[
                Citation(
                    raw_text="Part A",
                    citation_type="internal",
                    span_start=15,
                    span_end=21,
                    annex_part="A",
                )
            ],
        ),
    ]
    _run_resolver_only(units)

    citations = units[-1].citations
    assert len(citations) == 1
    assert citations[0].annex == "I"
    assert citations[0].annex_part == "A"
    assert citations[0].target_node_id == "annex-I.part-A"


def test_context_resolver_missing_annex_target_gets_null() -> None:
    units = [
        _make_unit("annex-I", "annex", annex_number="I", text="ANNEX I"),
        _make_unit("annex-I.item-1", "annex_item", annex_number="I", text="as provided in Annex V."),
    ]
    _run_enrichment(units)

    citations = units[-1].citations
    assert len(citations) == 1
    assert citations[0].annex == "V"
    assert citations[0].target_node_id is None


def test_article_pair_still_emits_two_citations() -> None:
    units = [_make_unit("u1", "paragraph", text="Articles 13 and 14 shall apply.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    assert {c.article_label for c in citations} == {"13", "14"}
