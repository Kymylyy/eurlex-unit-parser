#!/usr/bin/env python3
"""Legacy compatibility wrapper for batch runner CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eurlex_unit_parser.batch.runner import (  # noqa: E402
    download_html,
    filename_from_entry,
    main,
    parse_html,
    run_batch,
    run_coverage,
    stable_hash,
    to_repo_relative,
)

__all__ = [
    "download_html",
    "filename_from_entry",
    "main",
    "parse_html",
    "run_batch",
    "run_coverage",
    "stable_hash",
    "to_repo_relative",
]


if __name__ == "__main__":
    main()
