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
    assert citations[0].article_label == "6"
    assert citations[0].paragraph == 1
    assert citations[0].target_node_id == "art-6.par-1"


def test_internal_article_first_point() -> None:
    units = [_make_unit("u1", "paragraph", text="See Article 2(1), point (b).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 2
    assert citations[0].article_label == "2"
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
    assert citations[0].article_label == "2"
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
    assert citations[0].act_year == 2016
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
    assert citations[0].article_label == "6"
    assert citations[0].paragraph == 1
    assert citations[0].point == "c"
    assert citations[0].target_node_id == "art-6.par-1.pt-c"
    assert citations[0].act_year == 2016
    assert citations[0].celex == "32016R0679"


def test_external_old_directive_format() -> None:
    units = [_make_unit("u1", "paragraph", text="as required by Directive 95/46/EC.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].act_type == "directive"
    assert citations[0].act_number == "95/46"
    assert citations[0].act_year == 1995
    assert citations[0].celex == "31995L0046"


def test_external_old_regulation_no_format() -> None:
    units = [_make_unit("u1", "paragraph", text="pursuant to Regulation (EC) No 45/2001.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].act_type == "regulation"
    assert citations[0].act_number == "45/2001"
    assert citations[0].act_year == 2001
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
    assert citations[0].article_label == "5"
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
    assert citations[0].article_label == "3"
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


def test_external_point_first_keeps_point() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text="as defined in point (1) of Article 4(1) of Regulation (EU) No 575/2013.",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].article == 4
    assert citations[0].article_label == "4"
    assert citations[0].paragraph == 1
    assert citations[0].point == "1"
    assert citations[0].act_year == 2013
    assert citations[0].celex == "32013R0575"


def test_internal_article_with_letter_suffix() -> None:
    units = [_make_unit("u1", "paragraph", text="as referred to in Article 6a(1).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 6
    assert citations[0].article_label == "6a"
    assert citations[0].paragraph == 1
    assert citations[0].target_node_id == "art-6a.par-1"


def test_internal_point_range_article_first() -> None:
    units = [_make_unit("u1", "paragraph", text="entities referred to in Article 2(1), points (a) to (d).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].article == 2
    assert citations[0].paragraph == 1
    assert citations[0].point_range == ("a", "d")


def test_internal_subparagraph_reference() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in the first subparagraph.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].subparagraph_ordinal == "first"


def test_internal_subparagraph_pair() -> None:
    units = [_make_unit("u1", "paragraph", text="the first and second subparagraphs of this paragraph apply.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    ordinals = sorted(c.subparagraph_ordinal for c in citations)
    assert ordinals == ["first", "second"]


def test_internal_chapter_section_title() -> None:
    units = [_make_unit("u1", "paragraph", text="as laid down in Chapter IV and Section II of Title III.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 3
    assert citations[0].chapter == "IV"
    assert citations[1].section == "II"
    assert citations[2].title_ref == "III"


def test_internal_this_chapter_and_this_paragraph() -> None:
    units = [_make_unit("u1", "paragraph", text="for the purposes of this Chapter and this paragraph.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    assert citations[0].chapter == "THIS"
    assert citations[1].raw_text.lower() == "this paragraph"


def test_internal_annex_references() -> None:
    units = [_make_unit("u1", "paragraph", text="as specified in Annex I and Annex VI, Part A and Section A of Annex I.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 3
    assert citations[0].annex == "I"
    assert citations[1].annex == "VI"
    assert citations[1].annex_part == "A"
    assert citations[2].annex == "I"
    assert citations[2].section == "A"


def test_internal_multiple_annexes() -> None:
    units = [_make_unit("u1", "paragraph", text="requirements set out in Annexes II and III.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    assert {c.annex for c in citations} == {"II", "III"}


def test_external_decision_formats() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text=(
                "as required by Decision (EU) 2024/1689, Council Decision 1999/468/EC, "
                "Decision No 768/2008/EC and Council Framework Decision 2002/584/JHA."
            ),
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 4
    assert citations[0].celex == "32024D1689"
    assert citations[1].celex == "31999D0468"
    assert citations[2].celex == "32008D0768"
    assert citations[3].celex is None
    assert citations[3].act_type == "decision"
    assert citations[0].act_year == 2024
    assert citations[1].act_year == 1999
    assert citations[2].act_year == 2008
    assert citations[3].act_year == 2002


def test_treaty_references() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text=(
                "under Article 16(2) TFEU, Article 2 TEU, Article 8(1) of the Charter of Fundamental Rights, "
                "and Protocol No 21."
            ),
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 4
    assert citations[0].treaty_code == "TFEU"
    assert citations[1].treaty_code == "TEU"
    assert citations[2].treaty_code == "CHARTER"
    assert citations[3].treaty_code == "PROTOCOL"


def test_connective_phrase_annotation() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text="entities referred to in Article 6(1) and rules laid down in Chapter II shall apply.",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    assert citations[0].connective_phrase == "referred to in"
    assert citations[1].connective_phrase == "laid down in"


def test_connective_phrase_missing_is_none() -> None:
    units = [_make_unit("u1", "paragraph", text="Article 6(1) applies.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].connective_phrase is None


def test_external_paragraph_ordinal() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text="Article 108, second paragraph, of Directive (EU) 2015/2366.",
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].article == 108
    assert citations[0].paragraph == 2
    assert citations[0].target_node_id == "art-108.par-2"
    assert citations[0].act_type == "directive"
    assert citations[0].act_number == "2015/2366"
    assert citations[0].act_year == 2015
    assert citations[0].celex == "32015L2366"


def test_external_point_first_subparagraph() -> None:
    units = [
        _make_unit(
            "u1",
            "paragraph",
            text=(
                "point (b) of the first subparagraph of Article 36(1) of Regulation (EU) 2016/679."
            ),
        )
    ]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].article == 36
    assert citations[0].paragraph == 1
    assert citations[0].subparagraph_ordinal == "first"
    assert citations[0].point == "b"
    assert citations[0].target_node_id == "art-36.par-1.subpar-1.pt-b"
    assert citations[0].celex == "32016R0679"


def test_internal_article_enumeration() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in Articles 3, 5 and 6.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 3
    assert {c.article_label for c in citations} == {"3", "5", "6"}


def test_internal_article_enumeration_with_suffix() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in Articles 40a and 41.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    assert {c.article_label for c in citations} == {"40a", "41"}


def test_internal_article_multi_paragraph() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in Article 12(5) and (7).")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    paragraphs = sorted(c.paragraph for c in citations)
    assert paragraphs == [5, 7]
    assert {c.target_node_id for c in citations} == {"art-12.par-5", "art-12.par-7"}


def test_relative_reference_this_decision() -> None:
    units = [_make_unit("u1", "paragraph", text="as set out in this Decision.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "internal"
    assert citations[0].raw_text == "this Decision"


def test_paragraph_range() -> None:
    units = [_make_unit("u1", "paragraph", text="as referred to in paragraphs 2 to 4.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].paragraph_range == (2, 4)


def test_external_old_directive_eec_format() -> None:
    units = [_make_unit("u1", "paragraph", text="as required by Directive 91/250/EEC.")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].citation_type == "eu_legislation"
    assert citations[0].act_type == "directive"
    assert citations[0].act_number == "91/250"
    assert citations[0].act_year == 1991
    assert citations[0].celex == "31991L0250"


def test_span_offsets_internal_and_external() -> None:
    units = [
        _make_unit("u1", "paragraph", text="as set out in Article 6(1)."),
        _make_unit(
            "u2",
            "paragraph",
            text="Article 6(1) of Regulation (EU) 2016/679 applies.",
        ),
    ]
    _run_enrichment(units)

    internal = units[0].citations[0]
    internal_start = units[0].text.index("Article 6(1)")
    internal_end = internal_start + len("Article 6(1)")
    assert internal.span_start == internal_start
    assert internal.span_end == internal_end

    external = units[1].citations[0]
    external_start = units[1].text.index("Article 6(1) of Regulation (EU) 2016/679")
    external_end = external_start + len("Article 6(1) of Regulation (EU) 2016/679")
    assert external.span_start == external_start
    assert external.span_end == external_end


def test_empty_text_unit_has_no_citations() -> None:
    units = [_make_unit("u1", "paragraph", text="")]
    _run_enrichment(units)

    assert units[0].citations == []


def test_internal_paragraph_of_this_article_single_match() -> None:
    units = [_make_unit("u1", "paragraph", text="criteria referred to in paragraph 1 of this Article")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].raw_text == "paragraph 1 of this Article"
    assert citations[0].paragraph == 1


def test_internal_point_of_subparagraph_of_paragraph() -> None:
    units = [_make_unit("u1", "paragraph", text="point (a) of the first subparagraph of paragraph 2")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    citation = citations[0]
    assert citation.point == "a"
    assert citation.subparagraph_ordinal == "first"
    assert citation.paragraph == 2


def test_internal_point_enumeration() -> None:
    units = [_make_unit("u1", "paragraph", text="points (a), (b) and (c)")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 3
    assert [citation.point for citation in citations] == ["a", "b", "c"]


def test_internal_subparagraph_comma_point() -> None:
    units = [_make_unit("u1", "paragraph", text="the first subparagraph, point (a)")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].subparagraph_ordinal == "first"
    assert citations[0].point == "a"


def test_internal_article_or() -> None:
    units = [_make_unit("u1", "paragraph", text="Article 43 or 44")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 2
    assert [citation.article_label for citation in citations] == ["43", "44"]


def test_internal_paragraph_enumeration() -> None:
    units = [_make_unit("u1", "paragraph", text="paragraphs 1, 2 or 3")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 3
    assert [citation.paragraph for citation in citations] == [1, 2, 3]


def test_internal_subparagraph_of_paragraph() -> None:
    units = [_make_unit("u1", "paragraph", text="the second subparagraph of paragraph 1")]
    _run_enrichment(units)

    citations = units[0].citations
    assert len(citations) == 1
    assert citations[0].subparagraph_ordinal == "second"
    assert citations[0].paragraph == 1
