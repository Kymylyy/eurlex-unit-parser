"""Unit tests for post-parse enrichment metadata."""

from __future__ import annotations

from eurlex_unit_parser import EUParser, Unit


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


def test_children_count_and_is_leaf() -> None:
    units = [
        _make_unit("art-1", "article", article_number="1"),
        _make_unit(
            "art-1.par-1",
            "paragraph",
            text="Entities shall:",
            parent_id="art-1",
            article_number="1",
            paragraph_number="1",
        ),
        _make_unit(
            "art-1.par-2",
            "paragraph",
            text="Leaf paragraph.",
            parent_id="art-1",
            article_number="1",
            paragraph_number="2",
        ),
        _make_unit(
            "art-1.par-1.pt-a",
            "point",
            text="A",
            parent_id="art-1.par-1",
            article_number="1",
            paragraph_number="1",
            point_label="a",
        ),
        _make_unit(
            "art-1.par-1.pt-b",
            "point",
            text="B",
            parent_id="art-1.par-1",
            article_number="1",
            paragraph_number="1",
            point_label="b",
        ),
        _make_unit(
            "art-1.par-1.pt-c",
            "point",
            text="C",
            parent_id="art-1.par-1",
            article_number="1",
            paragraph_number="1",
            point_label="c",
        ),
    ]

    _run_enrichment(units)
    by_id = {u.id: u for u in units}

    assert by_id["art-1"].children_count == 2
    assert by_id["art-1"].is_leaf is False
    assert by_id["art-1.par-1"].children_count == 3
    assert by_id["art-1.par-1"].is_leaf is False
    assert by_id["art-1.par-2"].children_count == 0
    assert by_id["art-1.par-2"].is_leaf is True


def test_is_stem() -> None:
    units = [
        _make_unit("art-1", "article", article_number="1"),
        _make_unit("art-1.par-1", "paragraph", text="Entities shall:", parent_id="art-1"),
        _make_unit("art-1.par-1.pt-a", "point", text="A", parent_id="art-1.par-1"),
        _make_unit("art-1.par-2", "paragraph", text="Entities shall.", parent_id="art-1"),
        _make_unit("art-1.par-2.pt-a", "point", text="A", parent_id="art-1.par-2"),
        _make_unit("art-1.par-3", "paragraph", text="Entities shall:", parent_id="art-1"),
    ]

    _run_enrichment(units)
    by_id = {u.id: u for u in units}

    assert by_id["art-1.par-1"].is_stem is True
    assert by_id["art-1.par-2"].is_stem is False
    assert by_id["art-1.par-3"].is_stem is False


def test_target_path() -> None:
    units = [
        _make_unit(
            "art-9.par-4.pt-a",
            "point",
            article_number="9",
            paragraph_number="4",
            point_label="a",
        ),
        _make_unit("art-5.par-2", "paragraph", article_number="5", paragraph_number="2"),
        _make_unit("art-3", "article", article_number="3"),
        _make_unit("recital-15", "recital", recital_number="15"),
        _make_unit("annex-I", "annex", annex_number="I"),
        _make_unit("annex-I.part-A.item-a", "annex_item", annex_number="I", annex_part="A"),
        _make_unit("art-9.par-idx.pt-b", "point", article_number="9", paragraph_index=1, point_label="b"),
        _make_unit("misc-1", "unknown_unit"),
    ]

    _run_enrichment(units)
    by_id = {u.id: u for u in units}

    assert by_id["art-9.par-4.pt-a"].target_path == "Art. 9(4)(a)"
    assert by_id["art-5.par-2"].target_path == "Art. 5(2)"
    assert by_id["art-3"].target_path == "Art. 3"
    assert by_id["recital-15"].target_path == "Recital 15"
    assert by_id["annex-I"].target_path == "Annex I"
    assert by_id["annex-I.part-A.item-a"].target_path == "Annex I, Part A"
    assert by_id["art-9.par-idx.pt-b"].target_path == "Art. 9(1)(b)"
    assert by_id["misc-1"].target_path is None


def test_article_heading_propagation_and_reset() -> None:
    units = [
        _make_unit("art-1", "article", article_number="1", heading="Protection and prevention"),
        _make_unit("art-1.par-1", "paragraph", parent_id="art-1", article_number="1"),
        _make_unit("art-1.par-1.pt-a", "point", parent_id="art-1.par-1", article_number="1"),
        _make_unit("recital-1", "recital", recital_number="1"),
        _make_unit("annex-I", "annex", annex_number="I"),
        _make_unit("art-2", "article", article_number="2", heading="Definitions"),
        _make_unit("art-2.par-1", "paragraph", parent_id="art-2", article_number="2"),
    ]

    _run_enrichment(units)
    by_id = {u.id: u for u in units}

    assert by_id["art-1"].article_heading == "Protection and prevention"
    assert by_id["art-1.par-1"].article_heading == "Protection and prevention"
    assert by_id["art-1.par-1.pt-a"].article_heading == "Protection and prevention"
    assert by_id["recital-1"].article_heading is None
    assert by_id["annex-I"].article_heading is None
    assert by_id["art-2"].article_heading == "Definitions"
    assert by_id["art-2.par-1"].article_heading == "Definitions"


def test_word_count_and_char_count() -> None:
    units = [
        _make_unit("u1", "paragraph", text="financial entities shall"),
        _make_unit("u2", "paragraph", text=""),
    ]

    _run_enrichment(units)
    by_id = {u.id: u for u in units}

    assert by_id["u1"].word_count == 3
    assert by_id["u1"].char_count == 24
    assert by_id["u2"].word_count == 0
    assert by_id["u2"].char_count == 0


def test_document_metadata() -> None:
    units = [
        _make_unit("document-title", "document_title", text="REGULATION (EU) 2022/2554"),
        _make_unit("art-1", "article", article_number="1", heading="Definitions"),
        _make_unit("art-1.par-1", "paragraph", parent_id="art-1", article_number="1"),
        _make_unit("art-1.par-1.pt-a", "point", parent_id="art-1.par-1", article_number="1"),
        _make_unit("art-1.par-1.pt-b", "point", parent_id="art-1.par-1", article_number="1"),
        _make_unit("art-2", "article", article_number="2", heading="General obligations"),
        _make_unit("art-2.par-1", "paragraph", parent_id="art-2", article_number="2"),
        _make_unit("art-2.par-2", "paragraph", parent_id="art-2", article_number="2"),
        _make_unit("art-2.par-2.pt-a", "point", parent_id="art-2.par-2", article_number="2"),
        _make_unit("annex-I", "annex", annex_number="I"),
        _make_unit("art-3", "article", article_number="3", is_amendment_text=True),
    ]

    parser = _run_enrichment(units)
    metadata = parser.document_metadata

    assert metadata is not None
    assert metadata.title == "REGULATION (EU) 2022/2554"
    assert metadata.total_units == 11
    assert metadata.total_articles == 3
    assert metadata.total_paragraphs == 3
    assert metadata.total_points == 3
    assert metadata.total_definitions == 2
    assert metadata.has_annexes is True
    assert metadata.amendment_articles == ["3"]


def test_document_metadata_detects_amendments_from_heading_and_child_units() -> None:
    units = [
        _make_unit("document-title", "document_title", text="REGULATION (EU) 2022/2554"),
        _make_unit(
            "art-59",
            "article",
            article_number="59",
            heading="Amendments to Regulation (EC) No 1060/2009",
        ),
        _make_unit(
            "art-59.par-1",
            "paragraph",
            parent_id="art-59",
            article_number="59",
            paragraph_number="1",
            is_amendment_text=True,
        ),
        _make_unit(
            "art-60",
            "article",
            article_number="60",
            heading="Amendments to Regulation (EU) No 648/2012",
        ),
        _make_unit(
            "art-60.par-1",
            "paragraph",
            parent_id="art-60",
            article_number="60",
            paragraph_number="1",
            is_amendment_text=True,
        ),
    ]

    parser = _run_enrichment(units)
    metadata = parser.document_metadata

    assert metadata is not None
    assert metadata.amendment_articles == ["59", "60"]
