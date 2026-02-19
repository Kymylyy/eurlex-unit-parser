"""Contract tests for generated JSON Schemas."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from jsonschema import Draft202012Validator

from eurlex_unit_parser.models import ValidationReport

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_output_schema_is_valid_and_accepts_example_payload() -> None:
    schema = _load_json(SCHEMAS_DIR / "eurlex-output.schema.json")
    payload = _load_json(REPO_ROOT / "examples" / "DORA.json")

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_output_schema_accepts_minimal_empty_payload() -> None:
    schema = _load_json(SCHEMAS_DIR / "eurlex-output.schema.json")
    payload = {
        "document_metadata": None,
        "summary_lsu": None,
        "summary_lsu_status": "disabled",
        "units": [],
    }

    Draft202012Validator(schema).validate(payload)


def test_validation_schema_is_valid_and_accepts_validation_report_payload() -> None:
    schema = _load_json(SCHEMAS_DIR / "eurlex-validation.schema.json")
    payload = asdict(ValidationReport(source_file="inline.html"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
