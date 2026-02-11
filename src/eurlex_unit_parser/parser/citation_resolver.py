"""Post-extraction context resolution for relative internal citations."""

from __future__ import annotations

from eurlex_unit_parser.models import Citation, Unit


class CitationResolverMixin:
    """Mixin resolving context-dependent internal references."""

    def _resolve_citations(self) -> None:
        for unit in self.units:
            for citation in unit.citations:
                self._resolve_relative_citation(citation, unit)

    def _resolve_relative_citation(self, citation: Citation, unit: Unit) -> None:
        if citation.citation_type != "internal":
            return

        raw_text = citation.raw_text.strip().lower()
        had_missing_article = citation.article_label is None
        had_missing_paragraph = citation.paragraph is None

        context_article, context_article_label = self._parse_article(unit.article_number)
        context_paragraph = self._parse_int(unit.paragraph_number)
        if context_paragraph is None:
            context_paragraph = unit.paragraph_index

        needs_article_from_context = (
            citation.article_label is None
            and (
                citation.paragraph is not None
                or citation.subparagraph_ordinal is not None
                or raw_text in {"this article", "this paragraph"}
            )
        )
        if needs_article_from_context and context_article_label is not None:
            citation.article = context_article
            citation.article_label = context_article_label

        if raw_text == "this article" and context_article_label is not None:
            citation.article = context_article
            citation.article_label = context_article_label

        if raw_text == "this paragraph" and context_article_label is not None:
            citation.article = context_article
            citation.article_label = context_article_label

        if citation.paragraph is None and (
            citation.subparagraph_ordinal is not None or raw_text == "this paragraph"
        ):
            if context_paragraph is not None:
                citation.paragraph = context_paragraph

        new_target: str | None
        if (
            citation.subparagraph_ordinal
            and citation.article_label is not None
            and citation.paragraph is not None
            and (had_missing_article or had_missing_paragraph)
        ):
            # EU drafting convention shifts subparagraph ordinals by one relative to parser IDs:
            # first -> paragraph node, second -> subpar-1, etc.
            new_target = self._to_context_shifted_subparagraph_node_id(
                article_label=citation.article_label,
                paragraph=citation.paragraph,
                subparagraph=citation.subparagraph_ordinal,
                point=citation.point,
            )
        else:
            new_target = self._to_node_id(
                article_label=citation.article_label,
                paragraph=citation.paragraph,
                point=citation.point,
                subparagraph=citation.subparagraph_ordinal,
            )

        if new_target is not None:
            citation.target_node_id = new_target

    @classmethod
    def _to_context_shifted_subparagraph_node_id(
        cls,
        article_label: str,
        paragraph: int,
        subparagraph: str,
        point: str | None,
    ) -> str | None:
        ordinal = cls._ordinal_to_int(subparagraph)
        if ordinal is None:
            return cls._to_node_id(
                article_label=article_label,
                paragraph=paragraph,
                point=point,
                subparagraph=subparagraph,
            )

        parts = [f"art-{article_label}", f"par-{paragraph}"]
        if ordinal > 1:
            parts.append(f"subpar-{ordinal - 1}")
        if point:
            parts.append(f"pt-{point}")
        return ".".join(parts)
