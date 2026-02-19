"""Compatibility tests for package public API and CLI module entrypoints."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_package_public_imports() -> None:
    import eurlex_unit_parser

    assert hasattr(eurlex_unit_parser, "EUParser")
    assert hasattr(eurlex_unit_parser, "DocumentMetadata")
    assert hasattr(eurlex_unit_parser, "LSUSummary")
    assert hasattr(eurlex_unit_parser, "LSUSummarySection")
    assert hasattr(eurlex_unit_parser, "Unit")
    assert hasattr(eurlex_unit_parser, "ValidationReport")
    assert hasattr(eurlex_unit_parser, "DownloadResult")
    assert hasattr(eurlex_unit_parser, "download_eurlex")
    assert hasattr(eurlex_unit_parser, "parse_html")
    assert hasattr(eurlex_unit_parser, "parse_file")
    assert hasattr(eurlex_unit_parser, "download_and_parse")
    assert hasattr(eurlex_unit_parser, "fetch_lsu_summary")
    assert hasattr(eurlex_unit_parser, "ParseResult")
    assert hasattr(eurlex_unit_parser, "JobResult")


def test_module_cli_help_commands() -> None:
    modules = [
        "eurlex_unit_parser.cli.parse",
        "eurlex_unit_parser.cli.coverage",
        "eurlex_unit_parser.cli.batch",
        "eurlex_unit_parser.cli.download",
    ]

    for module in modules:
        result = subprocess.run(
            [sys.executable, "-m", module, "--help"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
            env={"PYTHONPATH": str(ROOT / "src")},
        )
        assert result.returncode == 0, f"{module} failed: {result.stderr}"
        assert "usage:" in result.stdout.lower()
