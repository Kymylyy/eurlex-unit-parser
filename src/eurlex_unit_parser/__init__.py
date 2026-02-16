"""Public package API for eurlex-unit-parser."""

from eurlex_unit_parser.api import JobResult, ParseResult, download_and_parse, parse_file, parse_html
from eurlex_unit_parser.download.eurlex import DownloadResult, download_eurlex, extract_name_from_url
from eurlex_unit_parser.models import Citation, DocumentMetadata, Unit, ValidationReport
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
    "download_eurlex",
    "extract_name_from_url",
    "DownloadResult",
    "parse_html",
    "parse_file",
    "download_and_parse",
    "ParseResult",
    "JobResult",
    "Citation",
    "DocumentMetadata",
    "Unit",
    "ValidationReport",
    "remove_note_tags",
    "normalize_text",
    "strip_leading_label",
    "is_list_table",
    "get_cell_text",
]
