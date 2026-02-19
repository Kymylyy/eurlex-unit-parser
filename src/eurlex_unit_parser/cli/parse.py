"""CLI entrypoint for parsing single EUR-Lex HTML files."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from eurlex_unit_parser import EUParser
from eurlex_unit_parser.summary import (
    LSU_STATUS_DISABLED,
    fetch_lsu_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse EU Official Journal HTML files to JSON")
    parser.add_argument("--input", "-i", required=True, help="Path to input HTML file")
    parser.add_argument("--out", "-o", help="Path to output JSON file (default: out/json/<name>.json)")
    parser.add_argument(
        "--validation",
        "-v",
        nargs="?",
        const=True,
        default=True,
        help="Path to validation report JSON file (default: out/validation/<name>_validation.json)",
    )
    parser.add_argument("--no-validation", action="store_true", help="Disable validation report generation")
    parser.add_argument("--out-dir", default="out", help="Base output directory (default: out)")
    parser.add_argument("--coverage", action="store_true", help="Run coverage test after parsing")
    parser.add_argument(
        "--no-summary-lsu",
        action="store_true",
        help="Disable LSU summary fetch and emit `summary_lsu_status=disabled`.",
    )
    parser.add_argument(
        "--summary-lsu-lang",
        help="Optional two-letter language override for LSU summary fetch (default: auto from source HTML).",
    )
    parser.add_argument(
        "--celex",
        help="Optional CELEX override used for LSU summary fetch.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    base_name = input_path.stem
    out_dir = Path(args.out_dir)

    if args.out:
        output_path = Path(args.out)
    else:
        output_path = out_dir / "json" / f"{base_name}.json"

    if args.no_validation:
        validation_path = None
    elif args.validation is True:
        validation_path = out_dir / "validation" / f"{base_name}_validation.json"
    elif args.validation:
        validation_path = Path(args.validation)
    else:
        validation_path = None

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        raise SystemExit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    eu_parser = EUParser(source_file=str(input_path))
    units = eu_parser.parse(html_content)
    if args.no_summary_lsu:
        summary_lsu, summary_lsu_status = None, LSU_STATUS_DISABLED
    else:
        summary_lsu, summary_lsu_status = fetch_lsu_summary(
            html_content=html_content,
            source_file=str(input_path),
            celex=args.celex,
            language=args.summary_lsu_lang,
        )

    units_data = [asdict(u) for u in units]
    output_data = {
        "document_metadata": asdict(eu_parser.document_metadata) if eu_parser.document_metadata else None,
        "summary_lsu": asdict(summary_lsu) if summary_lsu else None,
        "summary_lsu_status": summary_lsu_status,
        "units": units_data,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Parsed {len(units)} units -> {output_path}")

    if validation_path:
        validation_path.parent.mkdir(parents=True, exist_ok=True)
        with open(validation_path, "w", encoding="utf-8") as f:
            json.dump(asdict(eu_parser.validation), f, ensure_ascii=False, indent=2)

        status = "PASS" if eu_parser.validation.is_valid() else "ISSUES FOUND"
        print(f"Validation: {status} -> {validation_path}")

    print("\nSummary:")
    for unit_type, count in sorted(eu_parser.validation.counts_parsed.items()):
        print(f"  {unit_type}: {count}")

    if args.coverage:
        print("\n" + "=" * 60)
        print("Running coverage test...")
        print("=" * 60)
        try:
            from eurlex_unit_parser.coverage import coverage_test, print_report, validate_hierarchy

            report = coverage_test(input_path, output_path)
            hierarchy = validate_hierarchy(units_data)
            passed = print_report(report, hierarchy, verbose=False)
            if not passed:
                raise SystemExit(1)
        except ImportError as e:
            print(f"Warning: Could not run coverage test: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
