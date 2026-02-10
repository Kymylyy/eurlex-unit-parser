"""Coverage module public API."""

from eurlex_unit_parser.coverage.core import compare_counters, coverage_test
from eurlex_unit_parser.coverage.extract_html import (
    build_full_html_text_by_section,
    build_naive_section_map,
    detect_format,
    extract_paragraph_texts_consolidated,
    extract_paragraph_texts_oj,
    extract_point_texts_consolidated,
    extract_point_texts_oj,
    normalize_whitespace,
)
from eurlex_unit_parser.coverage.extract_json import (
    build_json_section_texts,
    extract_json_all_texts,
    extract_json_paragraph_texts,
    extract_json_point_texts,
)
from eurlex_unit_parser.coverage.hierarchy import validate_hierarchy, validate_ordering
from eurlex_unit_parser.coverage.report import print_report

__all__ = [
    "build_full_html_text_by_section",
    "build_json_section_texts",
    "build_naive_section_map",
    "compare_counters",
    "coverage_test",
    "detect_format",
    "extract_json_all_texts",
    "extract_json_paragraph_texts",
    "extract_json_point_texts",
    "extract_paragraph_texts_consolidated",
    "extract_paragraph_texts_oj",
    "extract_point_texts_consolidated",
    "extract_point_texts_oj",
    "normalize_whitespace",
    "print_report",
    "validate_hierarchy",
    "validate_ordering",
]
