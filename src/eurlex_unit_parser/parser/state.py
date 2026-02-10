"""Shared parser state and common lifecycle helpers."""

from __future__ import annotations

from bs4 import BeautifulSoup

from eurlex_unit_parser.models import Unit, ValidationReport


class ParserStateMixin:
    """Shared parser state and common helper methods."""

    def __init__(self, source_file: str):
        self.source_file = source_file
        self.units: list[Unit] = []
        self.validation = ValidationReport(source_file=source_file)
        self._unit_ids: set[str] = set()
        self.is_consolidated = False
        self.soup: BeautifulSoup | None = None

    def _detect_format(self) -> None:
        if self.soup is None:
            self.is_consolidated = False
            return
        if self.soup.find("p", class_="title-article-norm"):
            self.is_consolidated = True
        elif self.soup.find("div", class_="grid-container"):
            self.is_consolidated = True
        else:
            self.is_consolidated = False

    def _count_expected_elements(self) -> None:
        if self.soup is None:
            self.validation.counts_expected = {}
            return
        self.validation.counts_expected = {
            "recitals": len(
                self.soup.find_all(
                    "div", class_="eli-subdivision", id=lambda x: x and x.startswith("rct_")
                )
            ),
            "articles": len(
                self.soup.find_all(
                    "div", class_="eli-subdivision", id=lambda x: x and x.startswith("art_")
                )
            ),
            "annexes": len(
                self.soup.find_all(
                    "div", class_="eli-container", id=lambda x: x and x.startswith("anx_")
                )
            ),
        }

    def _count_parsed_elements(self) -> None:
        counts: dict[str, int] = {}
        for unit in self.units:
            counts[unit.type] = counts.get(unit.type, 0) + 1
        self.validation.counts_parsed = counts

    def _add_unit(self, unit: Unit) -> None:
        if unit.id in self._unit_ids:
            suffix = 1
            base_id = unit.id
            while unit.id in self._unit_ids:
                unit.id = f"{base_id}_{suffix}"
                suffix += 1
        self._unit_ids.add(unit.id)
        self.units.append(unit)
