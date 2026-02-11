"""Parser engine that orchestrates the full parsing pipeline."""

from __future__ import annotations

from bs4 import BeautifulSoup

from eurlex_unit_parser.models import Unit
from eurlex_unit_parser.parser.annex import AnnexParserMixin
from eurlex_unit_parser.parser.citations import CitationExtractorMixin
from eurlex_unit_parser.parser.citation_resolver import CitationResolverMixin
from eurlex_unit_parser.parser.consolidated import ConsolidatedParserMixin
from eurlex_unit_parser.parser.enrichment import EnrichmentMixin
from eurlex_unit_parser.parser.oj import OJParserMixin
from eurlex_unit_parser.parser.state import ParserStateMixin
from eurlex_unit_parser.parser.tables import TablesParserMixin
from eurlex_unit_parser.parser.validation import ValidationMixin


class EUParser(
    OJParserMixin,
    ConsolidatedParserMixin,
    AnnexParserMixin,
    TablesParserMixin,
    ValidationMixin,
    CitationExtractorMixin,
    CitationResolverMixin,
    EnrichmentMixin,
    ParserStateMixin,
):
    """Parser for EU Official Journal HTML files."""

    def parse(self, html_content: str) -> list[Unit]:
        self.soup = BeautifulSoup(html_content, "lxml")

        self._detect_format()
        self._count_expected_elements()
        self._parse_document_title()
        self._parse_recitals()

        if self.is_consolidated:
            self._parse_articles_consolidated()
        else:
            self._parse_articles()

        self._parse_annexes()
        self._count_parsed_elements()
        self._validate()
        self._enrich()

        return self.units
