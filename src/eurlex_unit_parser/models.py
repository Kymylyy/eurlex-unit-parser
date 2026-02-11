"""Core data models for parsed legal units and validation reports."""

from dataclasses import MISSING, dataclass, field
from typing import Any, Optional


def schema_field(
    description: str,
    *,
    default: Any = MISSING,
    default_factory: Any = MISSING,
    json_schema: dict[str, Any] | None = None,
) -> Any:
    """Create a dataclass field with reusable JSON Schema metadata."""

    metadata: dict[str, Any] = {"description": description}
    if json_schema is not None:
        metadata["json_schema"] = json_schema

    kwargs: dict[str, Any] = {"metadata": metadata}
    if default is not MISSING:
        kwargs["default"] = default
    if default_factory is not MISSING:
        kwargs["default_factory"] = default_factory
    return field(**kwargs)


@dataclass
class Citation:
    """Represents one reference mention extracted from a unit's text."""

    raw_text: str = schema_field("Exact citation substring as it appears in `Unit.text`.")
    citation_type: str = schema_field(
        "Citation family: internal cross-reference or external EU act reference.",
        json_schema={"enum": ["internal", "eu_legislation"]},
    )
    span_start: int = schema_field("Inclusive character offset of citation start within `Unit.text`.")
    span_end: int = schema_field("Exclusive character offset of citation end within `Unit.text`.")
    article: Optional[int] = schema_field(default=None, description="Referenced article number if present.")
    article_label: Optional[str] = schema_field(
        default=None,
        description="Raw article label when alphanumeric (e.g. `6a`) cannot be represented as integer.",
    )
    paragraph: Optional[int] = schema_field(
        default=None,
        description="Referenced paragraph number if present.",
    )
    point: Optional[str] = schema_field(default=None, description="Referenced point label, e.g. `a`.")
    point_range: tuple[str, str] | None = schema_field(
        default=None,
        description="Inclusive point interval `(start, end)` for references such as `points (a) to (d)`.",
    )
    article_range: tuple[int, int] | None = schema_field(
        default=None,
        description="Inclusive article interval `(start, end)` when a range is detected.",
    )
    paragraph_range: tuple[int, int] | None = schema_field(
        default=None,
        description="Inclusive paragraph interval `(start, end)` when a range is detected.",
    )
    subparagraph_ordinal: Optional[str] = schema_field(
        default=None,
        description="Ordinal marker for subparagraph references, e.g. `first`, `second`.",
    )
    subparagraph_index: Optional[int] = schema_field(
        default=None,
        description="1-based subparagraph index derived from `subparagraph_ordinal` when resolvable.",
    )
    chapter: Optional[str] = schema_field(default=None, description="Referenced chapter label if present.")
    section: Optional[str] = schema_field(default=None, description="Referenced section label if present.")
    title_ref: Optional[str] = schema_field(default=None, description="Referenced title label if present.")
    annex: Optional[str] = schema_field(default=None, description="Referenced annex label, e.g. `I`.")
    annex_part: Optional[str] = schema_field(
        default=None,
        description="Referenced annex part label, e.g. `A`.",
    )
    treaty_code: Optional[str] = schema_field(
        default=None,
        description="Normalized treaty identifier for treaty references.",
        json_schema={
            "anyOf": [
                {"enum": ["TFEU", "TEU", "CHARTER", "TREATY_GENERIC", "PROTOCOL"]},
                {"type": "null"},
            ]
        },
    )
    connective_phrase: Optional[str] = schema_field(
        default=None,
        description="Leading connective phrase associated with the citation, if extracted.",
    )
    target_node_id: Optional[str] = schema_field(
        default=None,
        description="Best-effort target unit identifier resolved from citation components.",
    )
    act_year: Optional[int] = schema_field(
        default=None,
        description="Extracted year of an external EU act when available.",
    )
    act_type: Optional[str] = schema_field(
        default=None,
        description="Normalized external act type for `eu_legislation` references.",
        json_schema={
            "anyOf": [
                {"enum": ["regulation", "directive", "decision"]},
                {"type": "null"},
            ]
        },
    )
    act_number: Optional[str] = schema_field(
        default=None,
        description="External act number in slash notation, e.g. `2016/679`.",
    )
    celex: Optional[str] = schema_field(
        default=None,
        description="Derived CELEX identifier for recognized external EU acts.",
    )


@dataclass
class Unit:
    """Represents one parsed structural unit (title, recital, article, paragraph, point, annex item)."""

    id: str = schema_field("Stable hierarchical unit identifier, e.g. `art-5.par-1.pt-a`.")
    type: str = schema_field(
        "Unit kind emitted by the parser.",
        json_schema={
            "anyOf": [
                {
                    "enum": [
                        "document_title",
                        "recital",
                        "article",
                        "paragraph",
                        "subparagraph",
                        "intro",
                        "point",
                        "subpoint",
                        "subsubpoint",
                        "annex",
                        "annex_part",
                        "annex_item",
                        "unknown_unit",
                    ]
                },
                {"type": "string", "pattern": "^nested_[0-9]+$"},
            ]
        },
    )
    ref: Optional[str] = schema_field(
        description="Original label text from source markup, e.g. `1.` or `(a)`.",
    )
    text: str = schema_field("Normalized textual content for this unit.")
    parent_id: Optional[str] = schema_field(
        description="Parent unit identifier; null for root-level units.",
    )
    source_id: str = schema_field("Original EUR-Lex element identifier from HTML, if present.")
    source_file: str = schema_field("Path to source HTML file used for parsing.")

    article_number: Optional[str] = schema_field(
        default=None,
        description="Owning article number for article descendants.",
    )
    paragraph_number: Optional[str] = schema_field(
        default=None,
        description="Explicit paragraph number if present in legal text.",
    )
    paragraph_index: Optional[int] = schema_field(
        default=None,
        description="1-based positional paragraph index when no explicit paragraph number exists.",
    )
    subparagraph_index: Optional[int] = schema_field(
        default=None,
        description="1-based positional index of subparagraph within the parent paragraph.",
    )
    point_label: Optional[str] = schema_field(default=None, description="Normalized label of a `point` unit.")
    subpoint_label: Optional[str] = schema_field(
        default=None,
        description="Normalized label of a `subpoint` unit.",
    )
    subsubpoint_label: Optional[str] = schema_field(
        default=None,
        description="Normalized label of a `subsubpoint` unit.",
    )
    extra_labels: list[str] = schema_field(
        default_factory=list,
        description="Extra normalized labels for deeply nested point structures (`nested_N`).",
    )

    heading: Optional[str] = schema_field(
        default=None,
        description="Heading/subtitle text for article or annex-level units.",
    )
    annex_number: Optional[str] = schema_field(
        default=None,
        description="Annex identifier for annex-related units, e.g. `I`.",
    )
    annex_part: Optional[str] = schema_field(
        default=None,
        description="Annex part label for annex descendants, e.g. `A`.",
    )
    recital_number: Optional[str] = schema_field(
        default=None,
        description="Recital ordinal number for recital units.",
    )

    is_amendment_text: bool = schema_field(
        default=False,
        description="Whether the text belongs to amendatory language rather than normative body text.",
    )

    source_xpath: Optional[str] = schema_field(
        default=None,
        description="Optional source XPath for diagnostics and traceability.",
    )

    target_path: Optional[str] = schema_field(
        default=None,
        description="Computed canonical path label (e.g. `Art. 5(1)(a)` or `Annex I`).",
    )
    article_heading: Optional[str] = schema_field(
        default=None,
        description="Inherited article heading propagated during post-parse enrichment.",
    )
    children_count: int = schema_field(default=0, description="Number of direct child units.")
    is_leaf: bool = schema_field(default=True, description="True when `children_count == 0`.")
    is_stem: bool = schema_field(
        default=False,
        description="True for units ending with `:` and having child units.",
    )
    word_count: int = schema_field(default=0, description="Token count of `text` split by whitespace.")
    char_count: int = schema_field(default=0, description="Character count of normalized `text`.")
    citations: list[Citation] = schema_field(
        default_factory=list,
        description="Deterministically extracted citation objects in text order.",
    )


@dataclass
class ValidationReport:
    """Validation report describing parser integrity checks for one source file."""

    source_file: str = schema_field("Path of HTML file that produced this report.")
    counts_expected: dict[str, int] = schema_field(
        default_factory=dict,
        description="Expected structural counts inferred from source HTML markers.",
    )
    counts_parsed: dict[str, int] = schema_field(
        default_factory=dict,
        description="Actual counts by parsed unit type.",
    )
    sequence_gaps: list[dict[str, object]] = schema_field(
        default_factory=list,
        description="Detected sequence gaps (e.g. missing recital numbers).",
    )
    orphans: list[dict[str, object]] = schema_field(
        default_factory=list,
        description="Units whose `parent_id` does not resolve to an existing unit.",
    )
    unparsed_nodes: list[dict[str, object]] = schema_field(
        default_factory=list,
        description="Source nodes that were expected but not parsed into units.",
    )
    mismatched_labels: list[dict[str, object]] = schema_field(
        default_factory=list,
        description="Label mismatches discovered during validation checks.",
    )

    def is_valid(self) -> bool:
        return (
            not self.sequence_gaps
            and not self.orphans
            and not self.unparsed_nodes
            and not self.mismatched_labels
        )


@dataclass
class DocumentMetadata:
    """Document-level aggregate metadata computed from the final parsed unit list."""

    title: Optional[str] = schema_field(default=None, description="Detected legal act title text.")
    total_units: int = schema_field(default=0, description="Total number of units in `units`.")
    total_articles: int = schema_field(default=0, description="Count of units with `type == article`.")
    total_paragraphs: int = schema_field(default=0, description="Count of units with `type == paragraph`.")
    total_points: int = schema_field(default=0, description="Count of units with `type == point`.")
    total_definitions: int = schema_field(
        default=0,
        description="Count of definition points inferred from article headings.",
    )
    has_annexes: bool = schema_field(default=False, description="True when at least one annex unit exists.")
    amendment_articles: list[str] = schema_field(
        default_factory=list,
        description="Article numbers identified as amendatory articles.",
    )
