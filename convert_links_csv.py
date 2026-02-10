#!/usr/bin/env python3
"""Legacy compatibility wrapper for CSV -> JSONL links converter."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eurlex_unit_parser.batch.links_convert import (  # noqa: E402
    convert_csv_to_jsonl,
    csv_row_to_jsonl_entry,
    main,
)

__all__ = ["convert_csv_to_jsonl", "csv_row_to_jsonl_entry", "main"]


if __name__ == "__main__":
    main()
