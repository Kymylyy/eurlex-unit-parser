"""Citation extraction enrichment for parsed units."""

from __future__ import annotations

import re
from re import Match, Pattern
from typing import Callable

from eurlex_unit_parser.models import Citation


class CitationExtractorMixin:
    """Mixin implementing deterministic citation extraction."""

    _ACT_FRAGMENT = (
        r"(?P<act>(?:Council\s+)?(?:Commission\s+)?(?:Delegated\s+|Implementing\s+)?"
        r"(?P<act_kind>Regulation|Directive|Decision)\s+"
        r"(?:\((?:EU|EC|EEC)\)\s+)?(?:No\s+)?"
        r"(?P<act_part1>\d{2,4})/(?P<act_part2>\d+)"
        r"(?:/(?P<act_suffix>EU|EC|EEC))?)"
    )

    _EXTERNAL_WITH_ARTICLE_ARTICLE_FIRST: Pattern[str] = re.compile(
        rf"""
        \bArticle\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?:\s?\((?P<point_inline>[a-z0-9]+)\))?
        (?:,\s*point\s+\((?P<point_comma>[a-z0-9]+)\))?
        \s*,?\s*of\s+{_ACT_FRAGMENT}\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _EXTERNAL_WITH_ARTICLE_POINT_FIRST: Pattern[str] = re.compile(
        rf"""
        \bpoint\s+\((?P<point>[a-z0-9]+)\)\s+of\s+Article\s+(?P<article>\d+[a-z]?)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?:\s?\((?P<point_inline>[a-z0-9]+)\))?
        \s+of\s+{_ACT_FRAGMENT}\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _EXTERNAL_STANDALONE: Pattern[str] = re.compile(
        rf"""\b{_ACT_FRAGMENT}\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ARTICLE_POINT: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+)
        (?:\s?\((?P<paragraph>\d+)\))?
        \s*,\s*point\s+\((?P<point>[a-z0-9]+)\)
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_POINT_OF_ARTICLE: Pattern[str] = re.compile(
        r"""
        \bpoint\s+\((?P<point>[a-z0-9]+)\)\s+of\s+Article\s+(?P<article>\d+)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_ARTICLE_RANGE: Pattern[str] = re.compile(
        r"""\bArticles\s+(?P<range_start>\d+)\s+(?:to|and)\s+(?P<range_end>\d+)\b""",
        re.IGNORECASE,
    )

    _INTERNAL_ARTICLE_SIMPLE: Pattern[str] = re.compile(
        r"""
        \bArticle\s+(?P<article>\d+)
        (?:\s?\((?P<paragraph>\d+)\))?
        (?:\s?\((?P<point_inline>[a-z0-9]+)\))?
        (?=[^\w]|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _INTERNAL_PARAGRAPH: Pattern[str] = re.compile(r"""\bparagraph\s+(?P<paragraph>\d+)\b""", re.IGNORECASE)

    _RELATIVE_REFERENCE: Pattern[str] = re.compile(
        r"""\bthis\s+(?:Regulation|Directive|Article|paragraph)\b""",
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

        builders: list[tuple[Pattern[str], Callable[[Match[str], str], Citation | None]]] = [
            (self._EXTERNAL_WITH_ARTICLE_ARTICLE_FIRST, self._build_external_with_article),
            (self._EXTERNAL_WITH_ARTICLE_POINT_FIRST, self._build_external_with_article),
            (self._EXTERNAL_STANDALONE, self._build_external_standalone),
            (self._INTERNAL_ARTICLE_POINT, self._build_internal_article_point),
            (self._INTERNAL_POINT_OF_ARTICLE, self._build_internal_article_point),
            (self._INTERNAL_ARTICLE_RANGE, self._build_internal_article_range),
            (self._INTERNAL_ARTICLE_SIMPLE, self._build_internal_article_simple),
            (self._INTERNAL_PARAGRAPH, self._build_internal_paragraph),
            (self._RELATIVE_REFERENCE, self._build_relative_reference),
        ]

        for pattern, builder in builders:
            citations.extend(self._collect_matches(text, pattern, consumed_spans, builder))

        citations.sort(key=lambda citation: citation.span_start)
        return citations

    def _collect_matches(
        self,
        text: str,
        pattern: Pattern[str],
        consumed_spans: list[tuple[int, int]],
        builder: Callable[[Match[str], str], Citation | None],
    ) -> list[Citation]:
        built: list[Citation] = []
        matches = sorted(pattern.finditer(text), key=lambda match: (-(match.end() - match.start()), match.start()))

        for match in matches:
            span_start, span_end = match.span()
            if self._is_overlapping(span_start, span_end, consumed_spans):
                continue
            citation = builder(match, text)
            if citation is None:
                continue
            consumed_spans.append((span_start, span_end))
            built.append(citation)

        return built

    def _build_external_with_article(self, match: Match[str], text: str) -> Citation | None:
        span_start, span_end = match.span()
        act_type = self._normalize_act_type(match.group("act_kind"))
        if act_type is None:
            return None

        act_part1 = match.group("act_part1")
        act_part2 = match.group("act_part2")
        act_number = f"{act_part1}/{act_part2}"

        article = self._parse_article(match.group("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        point = self._normalize_point(
            match.groupdict().get("point_comma")
            or match.groupdict().get("point")
            or match.groupdict().get("point_inline")
        )

        celex = None
        parsed = self._parse_act_year_number(act_part1, act_part2)
        if parsed is not None:
            year, number = parsed
            celex = self._to_celex(act_type, year, number)

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="eu_legislation",
            span_start=span_start,
            span_end=span_end,
            article=article,
            paragraph=paragraph,
            point=point,
            target_node_id=self._to_node_id(article=article, paragraph=paragraph, point=point),
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
        if parsed is not None:
            year, number = parsed
            celex = self._to_celex(act_type, year, number)

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="eu_legislation",
            span_start=span_start,
            span_end=span_end,
            act_type=act_type,
            act_number=act_number,
            celex=celex,
        )

    def _build_internal_article_point(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        article = self._parse_article(match.group("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        point = self._normalize_point(match.groupdict().get("point"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article=article,
            paragraph=paragraph,
            point=point,
            target_node_id=self._to_node_id(article=article, paragraph=paragraph, point=point),
        )

    def _build_internal_article_range(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        range_start = int(match.group("range_start"))
        range_end = int(match.group("range_end"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article_range=(range_start, range_end),
            target_node_id=None,
        )

    def _build_internal_article_simple(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        article = self._parse_article(match.group("article"))
        paragraph = self._parse_int(match.groupdict().get("paragraph"))
        point = self._normalize_point(match.groupdict().get("point_inline"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            article=article,
            paragraph=paragraph,
            point=point,
            target_node_id=self._to_node_id(article=article, paragraph=paragraph, point=point),
        )

    def _build_internal_paragraph(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        paragraph = self._parse_int(match.group("paragraph"))

        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
            paragraph=paragraph,
            target_node_id=self._to_node_id(article=None, paragraph=paragraph, point=None),
        )

    def _build_relative_reference(self, match: Match[str], text: str) -> Citation:
        span_start, span_end = match.span()
        return Citation(
            raw_text=text[span_start:span_end],
            citation_type="internal",
            span_start=span_start,
            span_end=span_end,
        )

    @staticmethod
    def _is_overlapping(span_start: int, span_end: int, consumed_spans: list[tuple[int, int]]) -> bool:
        return any(span_start < consumed_end and span_end > consumed_start for consumed_start, consumed_end in consumed_spans)

    @staticmethod
    def _parse_article(article: str | None) -> int | None:
        if article is None or not article.isdigit():
            return None
        return int(article)

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

    @staticmethod
    def _to_node_id(article: int | None, paragraph: int | None, point: str | None) -> str | None:
        parts: list[str] = []
        if article is not None:
            parts.append(f"art-{article}")
        if paragraph is not None:
            parts.append(f"par-{paragraph}")
        if point:
            parts.append(f"pt-{point}")
        return ".".join(parts) if parts else None
