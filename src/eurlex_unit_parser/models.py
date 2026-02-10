"""Core data models for parsed legal units and validation reports."""

from dataclasses import dataclass, field
from typing import Optional


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
