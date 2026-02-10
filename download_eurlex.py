#!/usr/bin/env python3
"""Legacy compatibility wrapper for downloader API and CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eurlex_unit_parser.download.eurlex import download_eurlex, extract_name_from_url, main  # noqa: E402

__all__ = ["download_eurlex", "extract_name_from_url", "main"]


if __name__ == "__main__":
    main()
