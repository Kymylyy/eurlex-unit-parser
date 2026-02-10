"""CLI entrypoint for coverage checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict

from bs4 import BeautifulSoup

from eurlex_unit_parser.coverage import (
    build_full_html_text_by_section,
    build_json_section_texts,
    coverage_test,
    print_report,
    validate_hierarchy,
    validate_ordering,
)


class PhantomReport(TypedDict):
    total: int
    by_section: dict[str, list[str]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Test parser coverage")
    parser.add_argument("--input", "-i", help="Path to HTML file")
    parser.add_argument("--json", "-j", help="Path to JSON file (default: out/json/<name>.json)")
    parser.add_argument("--all", action="store_true", help="Test all HTML files in downloads/eur-lex/")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show details")
    parser.add_argument("--report", "-r", help="Save report to JSON file")
    parser.add_argument("--oracle", choices=["naive", "mirror"], default="naive", help="Coverage oracle to use")
    parser.add_argument("--no-phantom", action="store_true", help="Disable phantom text check")

    args = parser.parse_args()

    if args.all:
        html_dir = Path("downloads/eur-lex")
        html_files = list(html_dir.glob("*.html"))
    elif args.input:
        html_files = [Path(args.input)]
    else:
        parser.print_help()
        raise SystemExit(1)

    all_passed = True

    for html_path in html_files:
        if not html_path.exists():
            print(f"Error: HTML file not found: {html_path}", file=sys.stderr)
            continue

        json_path = Path(args.json) if args.json else Path("out/json") / f"{html_path.stem}.json"
        if not json_path.exists():
            print(f"Error: JSON file not found: {json_path}", file=sys.stderr)
            continue

        print(f"\n{'#' * 60}")
        print(f"# {html_path.name}")
        print(f"{'#' * 60}")

        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "lxml")
        with open(json_path, "r", encoding="utf-8") as f:
            units = json.load(f)

        report = coverage_test(html_path, json_path, oracle=args.oracle)

        phantom_report: PhantomReport | None = None
        if not args.no_phantom:
            full_html = build_full_html_text_by_section(soup)
            json_sections = build_json_section_texts(units)
            phantom_report = {"total": 0, "by_section": {}}
            for key, texts in json_sections.items():
                html_text = full_html.get(key, "")
                missing: list[str] = []
                for t in texts:
                    if t and t not in html_text:
                        missing.append(t[:100] + ("..." if len(t) > 100 else ""))
                phantom_report["by_section"][key] = missing
                phantom_report["total"] += len(missing)

        hierarchy = validate_hierarchy(units)
        ordering = validate_ordering(units)

        passed = print_report(report, hierarchy, args.verbose, phantom_report, ordering)
        all_passed = all_passed and passed

        if args.report and len(html_files) == 1:
            full_report = {
                "coverage": report,
                "hierarchy": hierarchy,
                "phantom": phantom_report,
                "ordering": ordering,
            }
            with open(args.report, "w", encoding="utf-8") as f:
                json.dump(full_report, f, ensure_ascii=False, indent=2)
            print(f"\nReport saved to: {args.report}")

    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
