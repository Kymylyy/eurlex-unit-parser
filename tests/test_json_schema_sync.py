"""Tests that schema artifacts stay synchronized with dataclass definitions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate_json_schemas.py"
SCHEMAS_DIR = REPO_ROOT / "schemas"
SCHEMA_FILES = ("eurlex-output.schema.json", "eurlex-validation.schema.json")


def _run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_schema_artifacts_match_generator_output(tmp_path: Path) -> None:
    generated_dir = tmp_path / "schemas"

    result = _run_generator("--out-dir", str(generated_dir))
    assert result.returncode == 0, result.stdout + result.stderr

    for file_name in SCHEMA_FILES:
        generated_bytes = (generated_dir / file_name).read_bytes()
        committed_bytes = (SCHEMAS_DIR / file_name).read_bytes()
        assert generated_bytes == committed_bytes, (
            f"Schema artifact '{file_name}' is out of date. "
            "Regenerate with: python3 scripts/generate_json_schemas.py"
        )


def test_check_mode_fails_when_artifacts_are_missing(tmp_path: Path) -> None:
    result = _run_generator("--check", "--out-dir", str(tmp_path / "missing"))

    assert result.returncode == 1
    assert "Schema artifacts out of date" in result.stdout


def test_check_mode_passes_for_generated_artifacts(tmp_path: Path) -> None:
    generated_dir = tmp_path / "schemas"

    generate_result = _run_generator("--out-dir", str(generated_dir))
    assert generate_result.returncode == 0, generate_result.stdout + generate_result.stderr

    check_result = _run_generator("--check", "--out-dir", str(generated_dir))
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
