"""Compatibility tests for legacy root entrypoints and imports."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_legacy_parse_imports() -> None:
    import parse_eu

    assert hasattr(parse_eu, "EUParser")
    assert hasattr(parse_eu, "DocumentMetadata")
    assert hasattr(parse_eu, "remove_note_tags")
    assert hasattr(parse_eu, "normalize_text")
    assert hasattr(parse_eu, "strip_leading_label")
    assert hasattr(parse_eu, "is_list_table")
    assert hasattr(parse_eu, "get_cell_text")


def test_legacy_coverage_imports() -> None:
    import test_coverage

    assert hasattr(test_coverage, "coverage_test")
    assert hasattr(test_coverage, "validate_hierarchy")
    assert hasattr(test_coverage, "validate_ordering")
    assert hasattr(test_coverage, "build_full_html_text_by_section")
    assert hasattr(test_coverage, "build_json_section_texts")
    assert hasattr(test_coverage, "normalize_whitespace")


def test_package_public_imports() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    import eurlex_unit_parser

    assert hasattr(eurlex_unit_parser, "EUParser")
    assert hasattr(eurlex_unit_parser, "DocumentMetadata")
    assert hasattr(eurlex_unit_parser, "Unit")
    assert hasattr(eurlex_unit_parser, "ValidationReport")
    assert hasattr(eurlex_unit_parser, "remove_note_tags")
    assert hasattr(eurlex_unit_parser, "normalize_text")


def test_legacy_cli_help_commands() -> None:
    scripts = [
        ROOT / "parse_eu.py",
        ROOT / "test_coverage.py",
        ROOT / "run_batch.py",
        ROOT / "convert_links_csv.py",
        ROOT / "download_eurlex.py",
    ]

    for script in scripts:
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
        )
        assert result.returncode == 0, f"{script.name} failed: {result.stderr}"
        assert "usage:" in result.stdout.lower()


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
