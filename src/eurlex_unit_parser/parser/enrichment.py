"""Post-parse enrichment logic for structural and document-level metadata."""

from __future__ import annotations

import re
from typing import Optional

from eurlex_unit_parser.models import DocumentMetadata, Unit


class EnrichmentMixin:
    """Mixin implementing post-parse deterministic enrichment."""

    def _enrich(self) -> None:
        """Post-parse enrichment: add structural metadata to all units."""
        self._build_parent_index()
        self._compute_children_counts()
        self._compute_is_stem()
        self._propagate_article_headings()
        self._compute_target_paths()
        self._compute_text_stats()
        self._compute_document_metadata()

    def _build_parent_index(self) -> None:
        self._unit_map: dict[str, Unit] = {u.id: u for u in self.units}
        self._children_map: dict[str, list[Unit]] = {}
        for unit in self.units:
            if unit.parent_id:
                self._children_map.setdefault(unit.parent_id, []).append(unit)

    def _compute_children_counts(self) -> None:
        for unit in self.units:
            children = self._children_map.get(unit.id, [])
            unit.children_count = len(children)
            unit.is_leaf = unit.children_count == 0

    def _compute_is_stem(self) -> None:
        for unit in self.units:
            text = unit.text or ""
            unit.is_stem = unit.children_count > 0 and text.rstrip().endswith(":")

    def _propagate_article_headings(self) -> None:
        current_heading: Optional[str] = None
        reset_types = {"document_title", "recital", "annex", "annex_part", "annex_item"}

        for unit in self.units:
            if unit.type in reset_types:
                current_heading = None
            if unit.type == "article":
                current_heading = unit.heading
            unit.article_heading = current_heading

    def _compute_target_paths(self) -> None:
        for unit in self.units:
            unit.target_path = self._build_target_path(unit)

    def _build_target_path(self, unit: Unit) -> Optional[str]:
        if unit.recital_number:
            return f"Recital {unit.recital_number}"

        if unit.annex_number:
            path = f"Annex {unit.annex_number}"
            if unit.annex_part:
                path += f", Part {unit.annex_part}"
            return path

        if not unit.article_number:
            return None

        parts = [f"Art. {unit.article_number}"]

        if unit.paragraph_number:
            parts.append(f"({unit.paragraph_number})")
        elif unit.paragraph_index is not None:
            parts.append(f"({unit.paragraph_index})")

        if unit.point_label:
            parts.append(f"({unit.point_label})")
        if unit.subpoint_label:
            parts.append(f"({unit.subpoint_label})")
        if unit.subsubpoint_label:
            parts.append(f"({unit.subsubpoint_label})")

        return "".join(parts)

    def _compute_text_stats(self) -> None:
        for unit in self.units:
            text = unit.text or ""
            unit.word_count = len(text.split()) if text else 0
            unit.char_count = len(text) if text else 0

    def _compute_document_metadata(self) -> None:
        title_unit = next((u for u in self.units if u.type == "document_title"), None)

        amendment_articles: list[str] = []
        seen_articles: set[str] = set()
        for unit in self.units:
            if unit.type == "article" and unit.is_amendment_text and unit.article_number:
                if unit.article_number not in seen_articles:
                    seen_articles.add(unit.article_number)
                    amendment_articles.append(unit.article_number)

        definition_article_numbers = {
            unit.article_number
            for unit in self.units
            if unit.type == "article"
            and unit.article_number
            and unit.heading
            and re.search(r"\bdefinitions?\b", unit.heading, re.IGNORECASE)
        }

        self.document_metadata = DocumentMetadata(
            title=title_unit.text if title_unit else None,
            total_units=len(self.units),
            total_articles=sum(1 for u in self.units if u.type == "article"),
            total_paragraphs=sum(1 for u in self.units if u.type == "paragraph"),
            total_points=sum(1 for u in self.units if u.type == "point"),
            total_definitions=sum(
                1
                for u in self.units
                if u.type == "point" and u.article_number in definition_article_numbers
            ),
            has_annexes=any(u.type == "annex" for u in self.units),
            amendment_articles=amendment_articles,
        )
