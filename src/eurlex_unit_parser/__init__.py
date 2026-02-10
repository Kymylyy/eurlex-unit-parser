"""Public package API for eurlex-unit-parser."""

from eurlex_unit_parser.models import DocumentMetadata, Unit, ValidationReport
from eurlex_unit_parser.parser.engine import EUParser
from eurlex_unit_parser.text_utils import (
    get_cell_text,
    is_list_table,
    normalize_text,
    remove_note_tags,
    strip_leading_label,
)

__all__ = [
    "EUParser",
    "DocumentMetadata",
    "Unit",
    "ValidationReport",
    "remove_note_tags",
    "normalize_text",
    "strip_leading_label",
    "is_list_table",
    "get_cell_text",
]
