"""CLI module exports."""

from eurlex_unit_parser.cli.batch import main as batch_main
from eurlex_unit_parser.cli.coverage import main as coverage_main
from eurlex_unit_parser.cli.download import main as download_main
from eurlex_unit_parser.cli.parse import main as parse_main

__all__ = ["parse_main", "coverage_main", "batch_main", "download_main"]
