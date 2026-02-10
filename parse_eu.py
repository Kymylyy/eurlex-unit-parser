#!/usr/bin/env python3
"""Legacy compatibility wrapper for parser API and CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eurlex_unit_parser import (  # noqa: E402
    Citation,
    DocumentMetadata,
    EUParser,
    Unit,
    ValidationReport,
    get_cell_text,
    is_list_table,
    normalize_text,
    remove_note_tags,
    strip_leading_label,
)
from eurlex_unit_parser.cli.parse import main  # noqa: E402

__all__ = [
    "EUParser",
    "Citation",
    "DocumentMetadata",
    "Unit",
    "ValidationReport",
    "remove_note_tags",
    "normalize_text",
    "strip_leading_label",
    "is_list_table",
    "get_cell_text",
    "main",
]


if __name__ == "__main__":
    main()
