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
        self._sync_subparagraph_index(citation)
        if citation.citation_type != "internal":
            return

        raw_text = citation.raw_text.strip().lower()
        had_missing_article = citation.article_label is None

        context_article, context_article_label = self._parse_article(unit.article_number)
        context_paragraph = self._parse_int(unit.paragraph_number)
        if context_paragraph is None:
            context_paragraph = unit.paragraph_index
        context_annex = unit.annex_number

        needs_article_from_context = (
            citation.article_label is None
            and (
                citation.paragraph is not None
                or citation.point is not None
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
            citation.point is not None
            or citation.subparagraph_ordinal is not None
            or raw_text == "this paragraph"
        ):
            if context_paragraph is not None:
                citation.paragraph = context_paragraph

        if citation.annex is None and citation.annex_part is not None and context_annex is not None:
            citation.annex = context_annex

        self._resolve_target_node_id(
            citation=citation,
            prefer_context_shifted_subparagraph=had_missing_article,
        )

    def _resolve_target_node_id(
        self,
        citation: Citation,
        prefer_context_shifted_subparagraph: bool = False,
    ) -> None:
        candidates: list[str] = []

        def add_candidate(candidate: str | None) -> None:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        shifted_target: str | None = None
        non_shifted_target: str | None = None
        if (
            citation.subparagraph_ordinal
            and citation.article_label is not None
            and citation.paragraph is not None
        ):
            shifted_target = self._to_context_shifted_subparagraph_node_id(
                article_label=citation.article_label,
                paragraph=citation.paragraph,
                subparagraph=citation.subparagraph_ordinal,
                point=citation.point,
            )
            non_shifted_target = self._to_node_id(
                article_label=citation.article_label,
                paragraph=citation.paragraph,
                point=citation.point,
                subparagraph=citation.subparagraph_ordinal,
                annex=citation.annex,
                annex_part=citation.annex_part,
            )

        if prefer_context_shifted_subparagraph and shifted_target is not None:
            add_candidate(shifted_target)
            add_candidate(non_shifted_target)
        else:
            add_candidate(
                self._to_node_id(
                    article_label=citation.article_label,
                    paragraph=citation.paragraph,
                    point=citation.point,
                    subparagraph=citation.subparagraph_ordinal,
                    annex=citation.annex,
                    annex_part=citation.annex_part,
                )
            )
            add_candidate(shifted_target)

        if citation.point is not None:
            add_candidate(
                self._to_node_id(
                    article_label=citation.article_label,
                    paragraph=citation.paragraph,
                    point=None,
                    subparagraph=citation.subparagraph_ordinal,
                    annex=citation.annex,
                    annex_part=citation.annex_part,
                )
            )
            if (
                citation.subparagraph_ordinal
                and citation.article_label is not None
                and citation.paragraph is not None
            ):
                add_candidate(
                    self._to_context_shifted_subparagraph_node_id(
                        article_label=citation.article_label,
                        paragraph=citation.paragraph,
                        subparagraph=citation.subparagraph_ordinal,
                        point=None,
                    )
                )

        if citation.annex is not None and citation.annex_part is not None:
            add_candidate(
                self._to_node_id(
                    article_label=None,
                    paragraph=None,
                    point=None,
                    subparagraph=None,
                    annex=citation.annex,
                    annex_part=None,
                )
            )

        for target in candidates:
            if self._target_exists(target):
                citation.target_node_id = target
                return

        citation.target_node_id = None

    def _sync_subparagraph_index(self, citation: Citation) -> None:
        if citation.subparagraph_ordinal is None:
            citation.subparagraph_index = None
            return
        citation.subparagraph_index = self._ordinal_to_int(citation.subparagraph_ordinal)

    def _target_exists(self, target_node_id: str | None) -> bool:
        if target_node_id is None:
            return False
        return target_node_id in self._unit_map

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
