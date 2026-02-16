"""Post-extraction context resolution for relative internal citations."""

from __future__ import annotations

import re

from eurlex_unit_parser.models import Citation, Unit


class CitationResolverMixin:
    """Mixin resolving context-dependent internal references."""

    _POINT_ENUMERATION_RAW = re.compile(
        r"""
        ^points\s+
        \([a-z0-9]+\)
        (?:\s*,\s*\([a-z0-9]+\))*
        \s*(?:,\s*)?(?:and|or)\s+\([a-z0-9]+\)
        $
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    _CLAUSE_BREAK = re.compile(r"[.;:]")
    _BARE_CONTEXTUAL_ACT_TYPES = {
        "that directive": "directive",
        "that regulation": "regulation",
        "that decision": "decision",
    }
    _INDEX_TO_ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}

    def _resolve_citations(self) -> None:
        for unit in self.units:
            for citation_index, citation in enumerate(unit.citations):
                self._resolve_relative_citation(citation, unit, citation_index)

    def _resolve_relative_citation(self, citation: Citation, unit: Unit, citation_index: int) -> None:
        self._sync_subparagraph_index(citation)
        if citation.citation_type != "internal":
            return

        raw_text = citation.raw_text.strip().lower()
        self._reclassify_bare_relative_act_reference(
            citation=citation,
            unit=unit,
            citation_index=citation_index,
            raw_text=raw_text,
        )
        if citation.citation_type != "internal":
            return

        had_missing_article = citation.article_label is None
        inferred_subparagraph_from_parent = False

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

        if self._is_standalone_point_enumeration(citation):
            anchor = self._find_preceding_internal_anchor(unit, citation, citation_index)
            if anchor is not None:
                self._apply_anchor_context(citation, anchor)
            else:
                inferred_subparagraph_from_parent = self._apply_parent_subparagraph_context(citation, unit)

        self._sync_subparagraph_index(citation)
        self._resolve_target_node_id(
            citation=citation,
            prefer_context_shifted_subparagraph=had_missing_article and not inferred_subparagraph_from_parent,
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

    def _reclassify_bare_relative_act_reference(
        self,
        citation: Citation,
        unit: Unit,
        citation_index: int,
        raw_text: str,
    ) -> None:
        target_act_type = self._BARE_CONTEXTUAL_ACT_TYPES.get(raw_text)
        if target_act_type is None:
            return

        antecedent = self._find_unique_preceding_eu_legislation_act(
            unit=unit,
            citation=citation,
            citation_index=citation_index,
            act_type=target_act_type,
        )
        if antecedent is None:
            return

        citation.citation_type = "eu_legislation"
        citation.act_type = antecedent.act_type
        citation.act_number = antecedent.act_number
        citation.act_year = antecedent.act_year
        citation.celex = antecedent.celex
        citation.target_node_id = None

    def _find_unique_preceding_eu_legislation_act(
        self,
        unit: Unit,
        citation: Citation,
        citation_index: int,
        act_type: str,
    ) -> Citation | None:
        unique_acts: dict[tuple[str, str], Citation] = {}
        for prior in reversed(unit.citations[:citation_index]):
            if prior.span_end > citation.span_start:
                continue
            if prior.citation_type != "eu_legislation":
                continue
            if prior.act_type != act_type or not prior.act_number:
                continue
            key = (act_type, prior.act_number)
            if key not in unique_acts:
                unique_acts[key] = prior

        if len(unique_acts) != 1:
            return None
        return next(iter(unique_acts.values()))

    def _is_standalone_point_enumeration(self, citation: Citation) -> bool:
        return bool(
            citation.citation_type == "internal"
            and citation.point is not None
            and self._POINT_ENUMERATION_RAW.fullmatch(citation.raw_text.strip())
        )

    def _find_preceding_internal_anchor(
        self,
        unit: Unit,
        citation: Citation,
        citation_index: int,
    ) -> Citation | None:
        if not unit.text:
            return None
        for prior in reversed(unit.citations[:citation_index]):
            if prior.span_end > citation.span_start:
                continue
            if prior.citation_type != "internal":
                continue
            if prior.article_label is None:
                continue
            between = unit.text[prior.span_end:citation.span_start]
            if self._CLAUSE_BREAK.search(between):
                continue
            return prior
        return None

    @staticmethod
    def _apply_anchor_context(citation: Citation, anchor: Citation) -> None:
        citation.article = anchor.article
        citation.article_label = anchor.article_label
        citation.paragraph = anchor.paragraph
        citation.subparagraph_ordinal = anchor.subparagraph_ordinal

    def _apply_parent_subparagraph_context(self, citation: Citation, unit: Unit) -> bool:
        parent_subparagraph = self._resolve_parent_subparagraph_ordinal(unit)
        if parent_subparagraph is None:
            return False
        citation.subparagraph_ordinal = parent_subparagraph
        citation.subparagraph_index = self._ordinal_to_int(parent_subparagraph)
        return True

    def _resolve_parent_subparagraph_ordinal(self, unit: Unit) -> str | None:
        parent_id = unit.parent_id
        while parent_id:
            parent = self._unit_map.get(parent_id)
            if parent is None:
                return None
            if parent.type == "subparagraph":
                if parent.subparagraph_index is None:
                    return None
                return self._INDEX_TO_ORDINAL.get(parent.subparagraph_index)
            parent_id = parent.parent_id
        return None

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
