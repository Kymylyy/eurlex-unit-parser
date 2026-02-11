"""Citation extraction enrichment for parsed units."""

from __future__ import annotations

import re
from re import Match, Pattern
from typing import Callable

from eurlex_unit_parser.models import Citation

BuilderResult = Citation | list[Citation] | None


class CitationExtractorMixin:
    """Mixin implementing deterministic citation extraction."""

    _ORDINALS = {"first", "second", "third", "fourth", "fifth"}

    _CONNECTIVE_PHRASES = [
        "acting in accordance with",
        "the procedure laid down in",
        "by way of derogation from",
        "falling within the scope of",
        "without prejudice to",
        "for the purposes of",
        "to the extent that",
        "in accordance with",
        "within the meaning of",
        "as provided for in",
        "as clarified in",
        "as referred to in",
        "in compliance with",
        "irrespective of",
        "as outlined in",
        "contrary to",
        "provided for in",
        "identified under",
        "established under",
        "established in",
        "having regard to",
        "pursuant to",
        "as defined in",
        "set out in",
        "laid down in",
        "as set out in",
        "as laid down in",
        "on the basis of",
        "except where",
        "in so far as",
        "referred to in",
        "specified in",
        "consistent with",
        "by virtue of",
        "by reason of",
        "notwithstanding",
        "approved by",
        "listed in",
        "subject to",
        "under",
    ]

    _ACT_FRAGMENT = (
        r"(?P<act>(?:Council\s+)?(?:Commission\s+)?(?:Delegated\s+|Implementing\s+)?"
        r"(?P<framework>Framework\s+)?(?P<act_kind>Regulation|Directive|Decision)\s+"
        r"(?:\((?:EU|EC|EEC)\)\s+)?(?:No\s+)?"
        r"(?P<act_part1>\d{2,4})/(?P<act_part2>\d+)"
        r"(?:/(?P<act_suffix>[A-Z]{2,4}))?)"
    )

    _EXTERNAL_WITH_ARTICLE_POINT_FIRST: Pattern[str] = re.compile(
        rf"""
        \bpoint\s+\((?P<point>[a-z0-9]+)\)\s+of\s+
        (?:the\s+(?P<subparagraph>first|second|third|fourth|fifth)\s+subparagraph\s+of\s+)?
        Article\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?:\s?\((?P<point_inline>[a-z0-9]+)\))?
        \s+of\s+{_ACT_FRAGMENT}\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _EXTERNAL_WITH_ARTICLE_ARTICLE_FIRST: Pattern[str] = re.compile(
        rf"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?:\s?\((?P<point_inline>[a-z0-9]+)\))?
        (?:\s*,\s*(?P<paragraph_ordinal>first|second|third|fourth|fifth)\s+paragraph)?
        (?:
            ,\s*point\s+\((?P<point_comma>[a-z0-9]+)\)
            |,\s*points\s+\((?P<point_range_start>[a-z0-9]+)\)\s+to\s+\((?P<point_range_end>[a-z0-9]+)\)
        )?
        \s*,?\s*of\s+{_ACT_FRAGMENT}\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _EXTERNAL_STANDALONE: Pattern[str] = re.compile(
        rf"""\b{_ACT_FRAGMENT}\b""",
        re.IGNORECASE,
    )

    _TREATY_TFEU_TEU_SHORT: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s+(?P<treaty>TFEU|TEU)\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _TREATY_LONG_TFEU: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s+of\s+the\s+Treaty\s+on\s+the\s+Functioning\s+of\s+the\s+European\s+Union\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _TREATY_LONG_TEU: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s+of\s+the\s+Treaty\s+on\s+European\s+Union\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _TREATY_LONG_GENERIC: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s+of\s+the\s+Treaty(?:\s+establishing\s+the\s+European\s+Community)?\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _TREATY_CHARTER: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s+of\s+the\s+Charter\s+of\s+Fundamental\s+Rights\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _TREATY_PROTOCOL: Pattern[str] = re.compile(
        r"""\bProtocol\s+No\s+(?P<protocol>\d+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ARTICLE_POINT_RANGE_ARTICLE_FIRST: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s*,\s*points\s+\((?P<point_start>[a-z0-9]+)\)\s+to\s+\((?P<point_end>[a-z0-9]+)\)
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_ARTICLE_POINT_RANGE_POINT_FIRST: Pattern[str] = re.compile(
        r"""
        \bpoints\s+\((?P<point_start>[a-z0-9]+)\)\s+to\s+\((?P<point_end>[a-z0-9]+)\)
        \s+of\s+Article\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_ARTICLE_POINT: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s*,\s*point\s+\((?P<point>[a-z0-9]+)\)
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_POINT_OF_ARTICLE: Pattern[str] = re.compile(
        r"""
        \bpoint\s+\((?P<point>[a-z0-9]+)\)\s+of\s+Article\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_ARTICLE_RANGE: Pattern[str] = re.compile(
        r"""\bArticles\s+(?P<range_start>\d+)\s+to\s+(?P<range_end>\d+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ARTICLE_ENUMERATION: Pattern[str] = re.compile(
        r"""\bArticles\s+(?P<enum_body>\d+[a-z]?(?:\s*,\s*\d+[a-z]?)*\s*(?:,\s*)?(?:and|or)\s+\d+[a-z]?)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ARTICLE_OR: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article1>\d+[a-z]?)
        (?:\s?\((?P<paragraph1>\d+)\))?
        \s+or\s+(?:Article\s+)?(?P<article2>\d+[a-z]?)
        (?:\s?\((?P<paragraph2>\d+)\))?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_ARTICLE_MULTI_PARAGRAPH: Pattern[str] = re.compile(
        r"""\bArticle\s+(?P<article>\d+[a-z]?)\s*\((?P<paragraph>\d+)\)\s+and\s+\((?P<paragraph_second>\d+)\)(?=[^\w]|$)""",
        re.IGNORECASE,
    )

    _INTERNAL_ARTICLE_SIMPLE: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?:\s?\((?P<point_inline>[a-z0-9]+)\))?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_PARAGRAPH_RANGE: Pattern[str] = re.compile(
        r"""\bparagraphs?\s+(?P<para_start>\d+)\s+(?:to|and|or)\s+(?P<para_end>\d+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_PARAGRAPH_ENUMERATION: Pattern[str] = re.compile(
        r"""\bparagraphs\s+(?P<enum_body>\d+(?:\s*,\s*\d+)*\s*(?:,\s*)?(?:and|or)\s+\d+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_PARAGRAPH_OF_THIS_ARTICLE: Pattern[str] = re.compile(
        r"""\bparagraph\s+(?P<paragraph>\d+)\s+of\s+this\s+Article\b""",
        re.IGNORECASE,
    )

    _INTERNAL_PARAGRAPH_SIMPLE: Pattern[str] = re.compile(
        r"""\bparagraph\s+(?P<paragraph>\d+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_POINT_ENUMERATION: Pattern[str] = re.compile(
        r"""
        \bpoints\s+
        (?P<enum_body>
            \([a-z0-9]+\)
            (?:\s*,\s*\([a-z0-9]+\))*
            \s*(?:,\s*)?(?:and|or)\s+\([a-z0-9]+\)
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_POINT_OF_SUBPARAGRAPH: Pattern[str] = re.compile(
        r"""
        \bpoint\s+\((?P<point>[a-z0-9]+)\)\s+of\s+
        the\s+(?P<ordinal>first|second|third|fourth|fifth)\s+subparagraph
        (?:\s+of\s+paragraph\s+(?P<paragraph>\d+))?
        (?:\s+of\s+this\s+Article)?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_SUBPARAGRAPH_COMMA_POINT: Pattern[str] = re.compile(
        r"""
        \bthe\s+(?P<ordinal>first|second|third|fourth|fifth)\s+subparagraph
        \s*,\s*point\s+\((?P<point>[a-z0-9]+)\)
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_SUBPARAGRAPH_PAIR_THIS_PARAGRAPH: Pattern[str] = re.compile(
        r"""
        \bthe\s+(?P<first_ord>first|second|third|fourth|fifth)
        \s+and\s+(?P<second_ord>first|second|third|fourth|fifth)
        \s+subparagraphs\s+of\s+this\s+paragraph\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_SUBPARAGRAPH_ARTICLE_FIRST: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s*,\s*(?P<ordinal>first|second|third|fourth|fifth)\s+subparagraph\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_SUBPARAGRAPH_OF_ARTICLE: Pattern[str] = re.compile(
        r"""
        \bthe\s+(?P<ordinal>first|second|third|fourth|fifth)\s+subparagraph
        \s+of\s+Article\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_SUBPARAGRAPH_OF_PARAGRAPH: Pattern[str] = re.compile(
        r"""
        \bthe\s+(?P<ordinal>first|second|third|fourth|fifth)\s+subparagraph
        \s+of\s+paragraph\s+(?P<paragraph>\d+)
        (?:\s+of\s+this\s+Article)?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_SUBPARAGRAPH_SIMPLE: Pattern[str] = re.compile(
        r"""\bthe\s+(?P<ordinal>first|second|third|fourth|fifth)\s+subparagraph\b""",
        re.IGNORECASE,
    )

    _INTERNAL_CHAPTER_SECTION_TITLE: Pattern[str] = re.compile(
        r"""\b(?P<kind>Chapter|Section|Title)\s+(?P<roman>[IVXLCDM]+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_THIS_CHAPTER_SECTION_TITLE: Pattern[str] = re.compile(
        r"""\bthis\s+(?P<kind>Chapter|Section|Title)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ANNEX_SECTION_OF_ANNEX: Pattern[str] = re.compile(
        r"""\bSection\s+(?P<section_letter>[A-Z])\s+of\s+Annex\s+(?P<annex>[IVXLCDM]+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ANNEX_WITH_PART: Pattern[str] = re.compile(
        r"""\bAnnex\s+(?P<annex>[IVXLCDM]+)\s*,?\s+Part\s+(?P<part>[A-Z])\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ANNEX_MULTIPLE: Pattern[str] = re.compile(
        r"""\bAnnexes\s+(?P<annex_first>[IVXLCDM]+)\s*,?\s+and\s+(?P<annex_second>[IVXLCDM]+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ANNEX_SIMPLE: Pattern[str] = re.compile(
        r"""\bAnnex(?:es)?\s+(?P<annex>[IVXLCDM]+)\b""",
        re.IGNORECASE,
    )

    _RELATIVE_REFERENCE: Pattern[str] = re.compile(
        r"""\b(?:this|that)\s+(?:Regulation|Directive|Decision|Article|paragraph)\b|\bthereof\b""",
        re.IGNORECASE,
    )

    def _extract_citations(self) -> None:
        for unit in self.units:
            if unit.is_amendment_text or not unit.text:
                unit.citations = []
                continue
            unit.citations = self._extract_citations_from_text(unit.text)

    def _extract_citations_from_text(self, text: str) -> list[Citation]:
        consumed_spans: list[tuple[int, int]] = []
        citations: list[Citation] = []

        builders: list[tuple[Pattern[str], Callable[[Match[str], str], BuilderResult]]] = [
            (self._EXTERNAL_WITH_ARTICLE_POINT_FIRST, self._build_external_with_article),
            (self._EXTERNAL_WITH_ARTICLE_ARTICLE_FIRST, self._build_external_with_article),
            (self._EXTERNAL_STANDALONE, self._build_external_standalone),
            (self._TREATY_TFEU_TEU_SHORT, self._build_treaty_short),
            (self._TREATY_LONG_TFEU, self._build_treaty_tfeu_long),
            (self._TREATY_LONG_TEU, self._build_treaty_teu_long),
            (self._TREATY_CHARTER, self._build_treaty_charter),
            (self._TREATY_LONG_GENERIC, self._build_treaty_generic),
            (self._TREATY_PROTOCOL, self._build_treaty_protocol),
            (self._INTERNAL_POINT_OF_SUBPARAGRAPH, self._build_internal_point_of_subparagraph),
            (self._INTERNAL_SUBPARAGRAPH_COMMA_POINT, self._build_internal_subparagraph_comma_point),
            (self._INTERNAL_SUBPARAGRAPH_OF_PARAGRAPH, self._build_internal_subparagraph_of_paragraph),
            (self._INTERNAL_ARTICLE_POINT_RANGE_ARTICLE_FIRST, self._build_internal_article_point_range),
            (self._INTERNAL_ARTICLE_POINT_RANGE_POINT_FIRST, self._build_internal_article_point_range),
            (self._INTERNAL_ARTICLE_POINT, self._build_internal_article_point),
            (self._INTERNAL_POINT_OF_ARTICLE, self._build_internal_article_point),
            (self._INTERNAL_ARTICLE_RANGE, self._build_internal_article_range),
            (self._INTERNAL_ARTICLE_ENUMERATION, self._build_internal_article_enumeration),
            (self._INTERNAL_ARTICLE_OR, self._build_internal_article_or),
            (self._INTERNAL_ARTICLE_MULTI_PARAGRAPH, self._build_internal_article_multi_paragraph),
            (self._INTERNAL_ARTICLE_SIMPLE, self._build_internal_article_simple),
            (self._INTERNAL_POINT_ENUMERATION, self._build_internal_point_enumeration),
            (self._INTERNAL_PARAGRAPH_ENUMERATION, self._build_internal_paragraph_enumeration),
            (self._INTERNAL_PARAGRAPH_OF_THIS_ARTICLE, self._build_internal_paragraph_of_this_article),
            (self._INTERNAL_PARAGRAPH_RANGE, self._build_internal_paragraph_range),
            (self._INTERNAL_PARAGRAPH_SIMPLE, self._build_internal_paragraph_simple),
            (self._INTERNAL_SUBPARAGRAPH_PAIR_THIS_PARAGRAPH, self._build_internal_subparagraph_pair),
            (self._INTERNAL_SUBPARAGRAPH_ARTICLE_FIRST, self._build_internal_subparagraph),
            (self._INTERNAL_SUBPARAGRAPH_OF_ARTICLE, self._build_internal_subparagraph),
            (self._INTERNAL_SUBPARAGRAPH_SIMPLE, self._build_internal_subparagraph),
            (self._INTERNAL_CHAPTER_SECTION_TITLE, self._build_internal_chapter_section_title),
            (self._INTERNAL_THIS_CHAPTER_SECTION_TITLE, self._build_internal_chapter_section_title),
            (self._INTERNAL_ANNEX_SECTION_OF_ANNEX, self._build_internal_annex),
            (self._INTERNAL_ANNEX_WITH_PART, self._build_internal_annex),
            (self._INTERNAL_ANNEX_MULTIPLE, self._build_internal_annex),
            (self._INTERNAL_ANNEX_SIMPLE, self._build_internal_annex),
            (self._RELATIVE_REFERENCE, self._build_relative_reference),
        ]

        for pattern, builder in builders:
            citations.extend(self._collect_matches(text, pattern, consumed_spans, builder))

        citations.sort(key=lambda citation: citation.span_start)
        self._annotate_connective_phrases(text, citations)
        return citations

    def _collect_matches(
        self,
        text: str,
        pattern: Pattern[str],
        consumed_spans: list[tuple[int, int]],
        builder: Callable[[Match[str], str], BuilderResult],
    ) -> list[Citation]:
        built: list[Citation] = []
        matches = sorted(pattern.finditer(text), key=lambda match: (-(match.end() - match.start()), match.start()))

        for match in matches:
            span_start, span_end = match.span()
            if self._is_overlapping(span_start, span_end, consumed_spans):
                continue

            result = builder(match, text)
            if result is None:
                continue

            citations = result if isinstance(result, list) else [result]
            if not citations:
                continue

            consumed_spans.append((span_start, span_end))
            built.extend(citations)

        return built

    def _build_external_with_article(self, match: Match[str], text: str) -> Citation | None:
        span_start, span_end = match.span()

        act_type = self._normalize_act_type(match.group("act_kind"))
        if act_type is None:
            return None

        act_part1 = match.group("act_part1")
        act_part2 = match.group("act_part2")
        act_number = f"{act_part1}/{act_part2}"

        article, article_label = self._parse_article(match.group("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        subparagraph_ordinal = self._normalize_ordinal(match.groupdict().get("subparagraph"))
        paragraph_ordinal = self._normalize_ordinal(match.groupdict().get("paragraph_ordinal"))
        if paragraph is None and paragraph_ordinal:
            paragraph = self._ordinal_to_int(paragraph_ordinal)

        point = self._normalize_point(
            match.groupdict().get("point")
            or match.groupdict().get("point_comma")
            or match.groupdict().get("point_inline")
        )
        point_range = self._parse_point_range(
            match.groupdict().get("point_range_start"),
            match.groupdict().get("point_range_end"),
        )

        celex = None
        parsed = self._parse_act_year_number(act_part1, act_part2)
        is_framework = bool((match.groupdict().get("framework") or "").strip())
        act_year = None
        if parsed is not None:
            year, number = parsed
            act_year = year
            if not is_framework:
                celex = self._to_celex(act_type, year, number)

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="eu_legislation",
            span_start=span_start,
            span_end=span_end,
            article=article,
            article_label=article_label,
            paragraph=paragraph,
            point=point,
            point_range=point_range,
            subparagraph_ordinal=subparagraph_ordinal,
            target_node_id=self._to_node_id(
                article_label=article_label,
                paragraph=paragraph,
                point=point,
                subparagraph=subparagraph_ordinal,
            ),
            act_year=act_year,
            act_type=act_type,
            act_number=act_number,
            celex=celex,
        )

    def _build_external_standalone(self, match: Match[str], text: str) -> Citation | None:
        span_start, span_end = match.span()

        act_type = self._normalize_act_type(match.group("act_kind"))
        if act_type is None:
            return None

        act_part1 = match.group("act_part1")
        act_part2 = match.group("act_part2")
        act_number = f"{act_part1}/{act_part2}"

        celex = None
        parsed = self._parse_act_year_number(act_part1, act_part2)
        is_framework = bool((match.groupdict().get("framework") or "").strip())
        act_year = None
        if parsed is not None:
            year, number = parsed
            act_year = year
            if not is_framework:
                celex = self._to_celex(act_type, year, number)

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="eu_legislation",
            span_start=span_start,
            span_end=span_end,
            act_year=act_year,
            act_type=act_type,
            act_number=act_number,
            celex=celex,
        )

    def _build_treaty_short(self, match: Match[str], text: str) -> Citation:
        treaty = (match.group("treaty") or "").upper()
        return self._build_treaty_citation(match, text, treaty_code=treaty)

    def _build_treaty_tfeu_long(self, match: Match[str], text: str) -> Citation:
        return self._build_treaty_citation(match, text, treaty_code="TFEU")

    def _build_treaty_teu_long(self, match: Match[str], text: str) -> Citation:
        return self._build_treaty_citation(match, text, treaty_code="TEU")

    def _build_treaty_generic(self, match: Match[str], text: str) -> Citation:
        return self._build_treaty_citation(match, text, treaty_code="TREATY_GENERIC")

    def _build_treaty_charter(self, match: Match[str], text: str) -> Citation:
        return self._build_treaty_citation(match, text, treaty_code="CHARTER")

    def _build_treaty_protocol(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="eu_legislation",
            span_start=span_start,
            span_end=span_end,
            treaty_code="PROTOCOL",
            act_number=match.group("protocol"),
        )

    def _build_treaty_citation(self, match: Match[str], text: str, treaty_code: str) -> Citation:
        span_start, span_end = match.span()
        article, article_label = self._parse_article(match.groupdict().get("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="eu_legislation",
            span_start=span_start,
            span_end=span_end,
            article=article,
            article_label=article_label,
            paragraph=paragraph,
            treaty_code=treaty_code,
            target_node_id=None,
        )

    def _build_internal_article_point_range(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()

        article, article_label = self._parse_article(match.group("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        point_range = self._parse_point_range(match.group("point_start"), match.group("point_end"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article=article,
            article_label=article_label,
            paragraph=paragraph,
            point_range=point_range,
            target_node_id=self._to_node_id(article_label=article_label, paragraph=paragraph, point=None),
        )

    def _build_internal_article_point(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()

        article, article_label = self._parse_article(match.group("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        point = self._normalize_point(match.groupdict().get("point"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article=article,
            article_label=article_label,
            paragraph=paragraph,
            point=point,
            target_node_id=self._to_node_id(article_label=article_label, paragraph=paragraph, point=point),
        )

    def _build_internal_article_range(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()

        range_start = self._parse_int(match.groupdict().get("range_start") or match.groupdict().get("enum_start"))
        range_end = self._parse_int(match.groupdict().get("range_end") or match.groupdict().get("enum_end"))

        article_range = None
        if range_start is not None and range_end is not None:
            article_range = (range_start, range_end)

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article_range=article_range,
            target_node_id=None,
        )

    def _build_internal_article_enumeration(self, match: Match[str], text: str) -> list[Citation]:
        span_start, span_end = match.span()
        enum_body = match.group("enum_body") or ""
        tokens = re.findall(r"\d+[a-z]?", enum_body)
        citations: list[Citation] = []
        for token in tokens:
            article, article_label = self._parse_article(token)
            if article_label is None:
                continue
            citations.append(
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    article=article,
                    article_label=article_label,
                    target_node_id=self._to_node_id(
                        article_label=article_label,
                        paragraph=None,
                        point=None,
                        subparagraph=None,
                    ),
                )
            )
        return citations

    def _build_internal_article_or(self, match: Match[str], text: str) -> list[Citation]:
        span_start, span_end = match.span()
        citations: list[Citation] = []

        article_tokens = [
            (match.groupdict().get("article1"), match.groupdict().get("paragraph1")),
            (match.groupdict().get("article2"), match.groupdict().get("paragraph2")),
        ]
        for article_token, paragraph_token in article_tokens:
            article, article_label = self._parse_article(article_token)
            if article_label is None:
                continue
            paragraph = self._parse_int(paragraph_token)
            citations.append(
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    article=article,
                    article_label=article_label,
                    paragraph=paragraph,
                    target_node_id=self._to_node_id(
                        article_label=article_label,
                        paragraph=paragraph,
                        point=None,
                        subparagraph=None,
                    ),
                )
            )

        return citations

    def _build_internal_article_multi_paragraph(self, match: Match[str], text: str) -> list[Citation]:
        span_start, span_end = match.span()
        article, article_label = self._parse_article(match.group("article"))
        first_paragraph = self._parse_int(match.group("paragraph"))
        second_paragraph = self._parse_int(match.group("paragraph_second"))
        citations: list[Citation] = []
        for paragraph in [first_paragraph, second_paragraph]:
            if paragraph is None:
                continue
            citations.append(
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    article=article,
                    article_label=article_label,
                    paragraph=paragraph,
                    target_node_id=self._to_node_id(
                        article_label=article_label,
                        paragraph=paragraph,
                        point=None,
                        subparagraph=None,
                    ),
                )
            )
        return citations

    def _build_internal_article_simple(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()

        article, article_label = self._parse_article(match.group("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        point = self._normalize_point(match.groupdict().get("point_inline"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article=article,
            article_label=article_label,
            paragraph=paragraph,
            point=point,
            target_node_id=self._to_node_id(article_label=article_label, paragraph=paragraph, point=point),
        )

    def _build_internal_point_enumeration(self, match: Match[str], text: str) -> list[Citation]:
        span_start, span_end = match.span()
        enum_body = match.group("enum_body") or ""
        points = re.findall(r"\(([a-z0-9]+)\)", enum_body)

        citations: list[Citation] = []
        for point_token in points:
            point = self._normalize_point(point_token)
            if point is None:
                continue
            citations.append(
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    point=point,
                    target_node_id=self._to_node_id(article_label=None, paragraph=None, point=point),
                )
            )

        return citations

    def _build_internal_paragraph_enumeration(self, match: Match[str], text: str) -> list[Citation]:
        span_start, span_end = match.span()
        enum_body = match.group("enum_body") or ""
        paragraphs = [self._parse_int(token) for token in re.findall(r"\d+", enum_body)]

        citations: list[Citation] = []
        for paragraph in paragraphs:
            if paragraph is None:
                continue
            citations.append(
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    paragraph=paragraph,
                    target_node_id=self._to_node_id(article_label=None, paragraph=paragraph, point=None),
                )
            )

        return citations

    def _build_internal_paragraph_of_this_article(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        paragraph = self._parse_int(match.group("paragraph"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            paragraph=paragraph,
            target_node_id=self._to_node_id(article_label=None, paragraph=paragraph, point=None),
        )

    def _build_internal_paragraph_range(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()

        para_start = self._parse_int(match.group("para_start"))
        para_end = self._parse_int(match.group("para_end"))

        paragraph_range = None
        if para_start is not None and para_end is not None:
            paragraph_range = (para_start, para_end)

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            paragraph_range=paragraph_range,
            target_node_id=None,
        )

    def _build_internal_paragraph_simple(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        paragraph = self._parse_int(match.group("paragraph"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            paragraph=paragraph,
            target_node_id=self._to_node_id(article_label=None, paragraph=paragraph, point=None),
        )

    def _build_internal_point_of_subparagraph(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        point = self._normalize_point(match.groupdict().get("point"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        ordinal = self._normalize_ordinal(match.groupdict().get("ordinal"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            paragraph=paragraph,
            point=point,
            subparagraph_ordinal=ordinal,
            target_node_id=self._to_node_id(
                article_label=None,
                paragraph=paragraph,
                point=point,
                subparagraph=ordinal,
            ),
        )

    def _build_internal_subparagraph_comma_point(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        point = self._normalize_point(match.groupdict().get("point"))
        ordinal = self._normalize_ordinal(match.groupdict().get("ordinal"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            point=point,
            subparagraph_ordinal=ordinal,
            target_node_id=self._to_node_id(
                article_label=None,
                paragraph=None,
                point=point,
                subparagraph=ordinal,
            ),
        )

    def _build_internal_subparagraph_of_paragraph(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        ordinal = self._normalize_ordinal(match.groupdict().get("ordinal"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            paragraph=paragraph,
            subparagraph_ordinal=ordinal,
            target_node_id=self._to_node_id(
                article_label=None,
                paragraph=paragraph,
                point=None,
                subparagraph=ordinal,
            ),
        )

    def _build_internal_subparagraph_pair(self, match: Match[str], text: str) -> list[Citation]:
        span_start, span_end = match.span()
        first_ord = self._normalize_ordinal(match.group("first_ord"))
        second_ord = self._normalize_ordinal(match.group("second_ord"))

        citations: list[Citation] = []
        if first_ord:
            citations.append(
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    subparagraph_ordinal=first_ord,
                )
            )
        if second_ord:
            citations.append(
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    subparagraph_ordinal=second_ord,
                )
            )
        return citations

    def _build_internal_subparagraph(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()

        article, article_label = self._parse_article(match.groupdict().get("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        ordinal = self._normalize_ordinal(match.group("ordinal"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article=article,
            article_label=article_label,
            paragraph=paragraph,
            subparagraph_ordinal=ordinal,
            target_node_id=self._to_node_id(
                article_label=article_label,
                paragraph=paragraph,
                point=None,
                subparagraph=ordinal,
            ),
        )

    def _build_internal_chapter_section_title(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()

        kind = (match.group("kind") or "").strip().lower()
        roman = match.groupdict().get("roman")
        if roman:
            roman = roman.upper()
        else:
            roman = "THIS"

        chapter = roman if kind == "chapter" else None
        section = roman if kind == "section" else None
        title_ref = roman if kind == "title" else None

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            chapter=chapter,
            section=section,
            title_ref=title_ref,
            target_node_id=None,
        )

    def _build_internal_annex(self, match: Match[str], text: str) -> BuilderResult:
        span_start, span_end = match.span()

        annex = match.groupdict().get("annex")
        if annex:
            annex = annex.upper()

        part = match.groupdict().get("part")
        if part:
            part = part.upper()

        section_letter = match.groupdict().get("section_letter")
        if section_letter:
            section_letter = section_letter.upper()

        first_annex = match.groupdict().get("annex_first")
        second_annex = match.groupdict().get("annex_second")

        if first_annex and second_annex:
            return [
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    annex=first_annex.upper(),
                    target_node_id=self._to_node_id(
                        article_label=None,
                        paragraph=None,
                        point=None,
                        subparagraph=None,
                        annex=first_annex.upper(),
                    ),
                ),
                Citation(
                    raw_text=text[span_start:span_end],
                    citation_type="internal",
                    span_start=span_start,
                    span_end=span_end,
                    annex=second_annex.upper(),
                    target_node_id=self._to_node_id(
                        article_label=None,
                        paragraph=None,
                        point=None,
                        subparagraph=None,
                        annex=second_annex.upper(),
                    ),
                ),
            ]

        target_node_id: str | None
        if section_letter and not part:
            target_node_id = None
        elif part:
            target_node_id = self._to_node_id(
                article_label=None,
                paragraph=None,
                point=None,
                subparagraph=None,
                annex=annex,
                annex_part=part,
            )
        else:
            target_node_id = self._to_node_id(
                article_label=None,
                paragraph=None,
                point=None,
                subparagraph=None,
                annex=annex,
            )

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            annex=annex,
            annex_part=part,
            section=section_letter,
            target_node_id=target_node_id,
        )

    def _build_relative_reference(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            target_node_id=None,
        )

    def _annotate_connective_phrases(self, text: str, citations: list[Citation]) -> None:
        for citation in citations:
            window_start = max(0, citation.span_start - 200)
            prefix = text[window_start:citation.span_start]
            normalized_prefix = self._normalize_phrase_text(prefix)

            best_match: str | None = None
            best_length = -1
            for phrase in self._CONNECTIVE_PHRASES:
                normalized_phrase = self._normalize_phrase_text(phrase)
                if not normalized_phrase:
                    continue
                if normalized_prefix.endswith(normalized_phrase) and len(normalized_phrase) > best_length:
                    best_match = phrase
                    best_length = len(normalized_phrase)

            citation.connective_phrase = best_match

    @staticmethod
    def _normalize_phrase_text(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _is_overlapping(span_start: int, span_end: int, consumed_spans: list[tuple[int, int]]) -> bool:
        return any(span_start < consumed_end and span_end > consumed_start for consumed_start, consumed_end in consumed_spans)

    @staticmethod
    def _parse_article(article: str | None) -> tuple[int | None, str | None]:
        if article is None:
            return None, None

        normalized = article.strip().lower()
        if not re.fullmatch(r"\d+[a-z]?", normalized):
            return None, None

        article_number_match = re.match(r"\d+", normalized)
        article_number = int(article_number_match.group()) if article_number_match else None
        return article_number, normalized

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if value is None or not value.isdigit():
            return None
        return int(value)

    @staticmethod
    def _normalize_point(value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @classmethod
    def _normalize_ordinal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized in cls._ORDINALS:
            return normalized
        return None

    @classmethod
    def _parse_point_range(cls, start: str | None, end: str | None) -> tuple[str, str] | None:
        normalized_start = cls._normalize_point(start)
        normalized_end = cls._normalize_point(end)
        if normalized_start is None or normalized_end is None:
            return None
        return normalized_start, normalized_end

    @staticmethod
    def _normalize_act_type(act_type: str | None) -> str | None:
        if act_type is None:
            return None
        normalized = act_type.strip().lower()
        if normalized == "regulation":
            return "regulation"
        if normalized == "directive":
            return "directive"
        if normalized == "decision":
            return "decision"
        return None

    @classmethod
    def _ordinal_to_int(cls, value: str) -> int | None:
        mapping = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
        normalized = value.strip().lower()
        return mapping.get(normalized)

    @staticmethod
    def _parse_act_year_number(part1: str, part2: str) -> tuple[int, int] | None:
        p1 = int(part1)
        p2 = int(part2)

        if 1900 < p1 <= 2100:
            return p1, p2
        if 1900 < p2 <= 2100:
            return p2, p1
        if p1 < 100 and p2 < 1000:
            return 1900 + p1, p2
        if p2 < 100 and p1 >= 100:
            return 1900 + p2, p1
        if p1 >= 1000 and p2 < 1000:
            return p1, p2
        return None

    @staticmethod
    def _to_celex(act_type: str, year: int, number: int) -> str | None:
        type_codes = {"regulation": "R", "directive": "L", "decision": "D"}
        type_code = type_codes.get(act_type)
        if type_code is None:
            return None
        return f"3{year:04d}{type_code}{number:04d}"

    @classmethod
    def _to_node_id(
        cls,
        article_label: str | None,
        paragraph: int | None,
        point: str | None,
        subparagraph: str | None = None,
        annex: str | None = None,
        annex_part: str | None = None,
    ) -> str | None:
        parts: list[str] = []
        if article_label is not None:
            parts.append(f"art-{article_label}")
        if paragraph is not None:
            parts.append(f"par-{paragraph}")
        if subparagraph and paragraph is not None:
            subparagraph_index = cls._ordinal_to_int(subparagraph)
            if subparagraph_index is not None:
                parts.append(f"subpar-{subparagraph_index}")
        if point:
            parts.append(f"pt-{point}")
        if annex:
            parts.append(f"annex-{annex}")
        if annex_part:
            parts.append(f"part-{annex_part}")
        return ".".join(parts) if parts else None
