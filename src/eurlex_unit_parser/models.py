"""Core data models for parsed legal units and validation reports."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Citation:
    """Represents a citation extracted from a unit text."""

    raw_text: str
    citation_type: str  # "internal" | "eu_legislation"
    span_start: int
    span_end: int
    article: Optional[int] = None
    article_label: Optional[str] = None
    paragraph: Optional[int] = None
    point: Optional[str] = None
    point_range: tuple[str, str] | None = None
    article_range: tuple[int, int] | None = None
    paragraph_range: tuple[int, int] | None = None
    subparagraph_ordinal: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    title_ref: Optional[str] = None
    annex: Optional[str] = None
    annex_part: Optional[str] = None
    treaty_code: Optional[str] = None  # "TFEU" | "TEU" | "CHARTER" | "TREATY_GENERIC" | "PROTOCOL"
    connective_phrase: Optional[str] = None
    target_node_id: Optional[str] = None
    act_year: Optional[int] = None
    act_type: Optional[str] = None  # "regulation" | "directive" | "decision"
    act_number: Optional[str] = None
    celex: Optional[str] = None


@dataclass
class Unit:
    """Represents a single parsed unit (recital, article, paragraph, point, etc.)."""

    id: str
    type: str
    ref: Optional[str]
    text: str
    parent_id: Optional[str]
    source_id: str
    source_file: str

    article_number: Optional[str] = None
    paragraph_number: Optional[str] = None
    paragraph_index: Optional[int] = None
    point_label: Optional[str] = None
    subpoint_label: Optional[str] = None
    subsubpoint_label: Optional[str] = None
    extra_labels: list = field(default_factory=list)

    heading: Optional[str] = None
    annex_number: Optional[str] = None
    annex_part: Optional[str] = None
    recital_number: Optional[str] = None

    is_amendment_text: bool = False

    source_xpath: Optional[str] = None

    # Post-parse enrichment fields
    target_path: Optional[str] = None
    article_heading: Optional[str] = None
    children_count: int = 0
    is_leaf: bool = True
    is_stem: bool = False
    word_count: int = 0
    char_count: int = 0
    citations: list[Citation] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Validation report for a parsed file."""

    source_file: str
    counts_expected: dict = field(default_factory=dict)
    counts_parsed: dict = field(default_factory=dict)
    sequence_gaps: list = field(default_factory=list)
    orphans: list = field(default_factory=list)
    unparsed_nodes: list = field(default_factory=list)
    mismatched_labels: list = field(default_factory=list)

    def is_valid(self) -> bool:
        return (
            not self.sequence_gaps
            and not self.orphans
            and not self.unparsed_nodes
            and not self.mismatched_labels
        )


@dataclass
class DocumentMetadata:
    """Document-level metadata computed from parsed units."""

    title: Optional[str] = None
    total_units: int = 0
    total_articles: int = 0
    total_paragraphs: int = 0
    total_points: int = 0
    total_definitions: int = 0
    has_annexes: bool = False
    amendment_articles: list[str] = field(default_factory=list)
