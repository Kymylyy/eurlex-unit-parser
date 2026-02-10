"""Convert candidate links from CSV format to JSONL used by batch runner."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def csv_row_to_jsonl_entry(row: dict[str, str]) -> dict[str, str]:
    return {
        "url": row["url"].strip(),
        "celex": row["celex"].strip(),
        "title": row["title"].strip(),
        "category_hint": row["category"].strip(),
        "source": "candidate_csv",
    }


def convert_csv_to_jsonl(csv_path: Path, jsonl_path: Path) -> int:
    count = 0
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, newline="", encoding="utf-8") as csv_file, open(
        jsonl_path, "w", encoding="utf-8"
    ) as jsonl_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            entry = csv_row_to_jsonl_entry(row)
            jsonl_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert EUR-Lex candidate CSV links to JSONL.")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Path to CSV input file")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Path to JSONL output file")
    args = parser.parse_args()

    count = convert_csv_to_jsonl(args.input, args.output)
    print(f"Converted {count} rows: {args.input} -> {args.output}")


if __name__ == "__main__":
    main()
