"""JSON extraction helpers used by coverage analysis."""

from __future__ import annotations

from collections import Counter

from eurlex_unit_parser.coverage.extract_html import normalize_whitespace


def extract_json_paragraph_texts(units: list[dict]) -> dict[str, Counter]:
    result = {"recitals": Counter()}

    for unit in units:
        text = unit.get("text", "").strip()
        if not text or len(text) <= 5:
            continue

        unit_type = unit.get("type", "")

        if unit_type == "recital":
            result["recitals"][text] += 1

        elif unit_type in ("paragraph", "subparagraph", "intro"):
            article_num = unit.get("article_number")
            if article_num:
                if article_num not in result:
                    result[article_num] = Counter()
                result[article_num][text] += 1

    return result


def extract_json_point_texts(units: list[dict]) -> dict[str, Counter]:
    result = {}

    for unit in units:
        text = unit.get("text", "").strip()
        if not text or len(text) <= 5:
            continue

        unit_type = unit.get("type", "")

        if unit_type in ("point", "subpoint", "subsubpoint") or unit_type.startswith("nested_"):
            article_num = unit.get("article_number")
            if article_num:
                if article_num not in result:
                    result[article_num] = Counter()
                result[article_num][text] += 1

    return result


def extract_json_all_texts(units: list[dict]) -> dict[str, Counter]:
    result = {"recitals": Counter()}

    for unit in units:
        text = unit.get("text", "").strip()
        if not text or len(text) <= 5:
            continue

        unit_type = unit.get("type", "")

        if unit_type == "recital":
            result["recitals"][text] += 1
        elif unit_type in (
            "paragraph",
            "subparagraph",
            "intro",
            "point",
            "subpoint",
            "subsubpoint",
            "unknown_unit",
        ) or unit_type.startswith("nested_"):
            article_num = unit.get("article_number")
            if article_num:
                if article_num not in result:
                    result[article_num] = Counter()
                result[article_num][text] += 1

    return result


def build_json_section_texts(units: list[dict]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}

    for unit in units:
        text = normalize_whitespace(unit.get("text", "") or "")
        if not text:
            continue

        unit_type = unit.get("type", "")

        if unit_type == "recital":
            key = "recitals"
        elif unit.get("annex_number") is not None:
            annex_num = unit.get("annex_number")
            key = f"annex_{annex_num}" if annex_num else "annex"
        elif unit.get("article_number") is not None:
            key = f"art_{unit.get('article_number')}"
        else:
            continue

        sections.setdefault(key, []).append(text)

    return sections
