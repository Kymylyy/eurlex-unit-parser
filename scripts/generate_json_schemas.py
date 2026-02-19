#!/usr/bin/env python3
"""Generate JSON Schema artifacts for parser output and validation report."""

from __future__ import annotations

import argparse
import json
import sys
import types
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Union, get_args, get_origin

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from eurlex_unit_parser.models import (  # noqa: E402
    DocumentMetadata,
    LSUSummary,
    LSUSummarySection,
    Unit,
    ValidationReport,
)

OUTPUT_SCHEMA_NAME = "eurlex-output.schema.json"
VALIDATION_SCHEMA_NAME = "eurlex-validation.schema.json"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _with_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        return {"anyOf": [schema, {"type": "null"}]}

    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        next_types = [schema_type, "null"]
        schema["type"] = sorted(set(next_types))
        return schema

    if isinstance(schema_type, list):
        schema_type.append("null")
        schema["type"] = sorted(set(schema_type))
        return schema

    return {"anyOf": [schema, {"type": "null"}]}


def _schema_for_type(annotation: Any, defs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if annotation in (Any, object):
        return {}

    origin = get_origin(annotation)

    if origin in (Union, types.UnionType):
        args = list(get_args(annotation))
        has_none = any(arg is type(None) for arg in args)
        non_none = [arg for arg in args if arg is not type(None)]

        if has_none and len(non_none) == 1:
            return _with_nullable(_schema_for_type(non_none[0], defs))

        return {"anyOf": [_schema_for_type(arg, defs) for arg in args]}

    if origin is list:
        args = get_args(annotation)
        item_schema = _schema_for_type(args[0], defs) if args else {}
        return {"type": "array", "items": item_schema}

    if origin is dict:
        args = get_args(annotation)
        value_schema = _schema_for_type(args[1], defs) if len(args) == 2 else {}
        return {"type": "object", "additionalProperties": value_schema}

    if origin is tuple:
        args = get_args(annotation)
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "items": _schema_for_type(args[0], defs)}
        return {
            "type": "array",
            "prefixItems": [_schema_for_type(arg, defs) for arg in args],
            "minItems": len(args),
            "maxItems": len(args),
        }

    primitive_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
    }
    if annotation in primitive_map:
        return primitive_map[annotation]

    if is_dataclass(annotation):
        class_name = annotation.__name__
        _ensure_dataclass_schema(annotation, defs)
        return {"$ref": f"#/$defs/{class_name}"}

    return {}


def _ensure_dataclass_schema(dataclass_type: type[Any], defs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    class_name = dataclass_type.__name__
    if class_name in defs:
        return defs[class_name]

    class_description = (dataclass_type.__doc__ or "").strip()
    schema: dict[str, Any] = {
        "title": class_name,
        "description": class_description,
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "required": [],
    }

    defs[class_name] = schema

    for model_field in fields(dataclass_type):
        field_schema = _schema_for_type(model_field.type, defs)

        field_description = model_field.metadata.get("description")
        if field_description:
            field_schema["description"] = field_description

        field_json_schema = model_field.metadata.get("json_schema")
        if field_json_schema:
            if any(key in field_json_schema for key in ("anyOf", "oneOf", "allOf", "not")):
                field_schema.pop("type", None)
            field_schema = {**field_schema, **field_json_schema}
            if field_description and "description" not in field_json_schema:
                field_schema["description"] = field_description

        schema["properties"][model_field.name] = field_schema
        schema["required"].append(model_field.name)

    return schema


def _base_schema(title: str, description: str) -> dict[str, Any]:
    return {
        "$schema": SCHEMA_DRAFT,
        "title": title,
        "description": description,
    }


def build_output_schema() -> dict[str, Any]:
    defs: dict[str, dict[str, Any]] = {}
    _ensure_dataclass_schema(Unit, defs)
    _ensure_dataclass_schema(DocumentMetadata, defs)
    _ensure_dataclass_schema(LSUSummarySection, defs)
    _ensure_dataclass_schema(LSUSummary, defs)

    schema = _base_schema(
        title="EUR-Lex Parser Output",
        description="JSON contract emitted by `eurlex-parse`.",
    )
    schema.update(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "document_metadata": {
                    "description": "Document-level summary metadata computed from parsed units.",
                    "anyOf": [
                        {"$ref": "#/$defs/DocumentMetadata"},
                        {"type": "null"},
                    ],
                },
                "summary_lsu": {
                    "description": "Optional LSU (Summaries of EU legislation) enrichment.",
                    "anyOf": [
                        {"$ref": "#/$defs/LSUSummary"},
                        {"type": "null"},
                    ],
                },
                "summary_lsu_status": {
                    "description": "LSU summary fetch status.",
                    "type": "string",
                    "enum": [
                        "ok",
                        "not_found",
                        "fetch_error",
                        "celex_missing",
                        "disabled",
                    ],
                },
                "units": {
                    "description": "Flat array of parsed legal units.",
                    "type": "array",
                    "items": {"$ref": "#/$defs/Unit"},
                },
            },
            "required": ["document_metadata", "summary_lsu", "summary_lsu_status", "units"],
            "$defs": defs,
        }
    )
    return schema


def build_validation_schema() -> dict[str, Any]:
    defs: dict[str, dict[str, Any]] = {}
    report_schema = _ensure_dataclass_schema(ValidationReport, defs)

    schema = _base_schema(
        title="EUR-Lex Validation Report",
        description="JSON contract emitted for parser validation diagnostics.",
    )
    schema.update(report_schema)
    schema["$defs"] = defs
    return schema


def render_schemas() -> dict[str, str]:
    schemas = {
        OUTPUT_SCHEMA_NAME: build_output_schema(),
        VALIDATION_SCHEMA_NAME: build_validation_schema(),
    }
    return {
        file_name: json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for file_name, schema in schemas.items()
    }


def write_schemas(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = render_schemas()
    for file_name, content in rendered.items():
        (out_dir / file_name).write_text(content, encoding="utf-8")


def check_schemas(out_dir: Path) -> bool:
    rendered = render_schemas()
    mismatched: list[str] = []

    for file_name, expected in rendered.items():
        output_path = out_dir / file_name
        if not output_path.exists():
            mismatched.append(file_name)
            continue

        actual = output_path.read_text(encoding="utf-8")
        if actual != expected:
            mismatched.append(file_name)

    if mismatched:
        files = ", ".join(sorted(mismatched))
        print(f"Schema artifacts out of date: {files}")
        print("Regenerate with: python3 scripts/generate_json_schemas.py")
        return False

    print(f"Schema artifacts are up to date in {out_dir}.")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate JSON Schema artifacts for parser models.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "schemas",
        help="Output directory for schema artifacts (default: schemas/).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that existing schema artifacts match generated output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = args.out_dir.resolve()

    if args.check:
        raise SystemExit(0 if check_schemas(out_dir) else 1)

    write_schemas(out_dir)
    print(f"Generated schema artifacts in {out_dir}.")


if __name__ == "__main__":
    main()
