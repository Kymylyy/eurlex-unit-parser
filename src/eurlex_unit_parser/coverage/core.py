"""Coverage core logic and counters comparison."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from eurlex_unit_parser.coverage.extract_html import (
    build_naive_section_map,
    detect_format,
    extract_paragraph_texts_consolidated,
    extract_paragraph_texts_oj,
    extract_point_texts_consolidated,
    extract_point_texts_oj,
)
from eurlex_unit_parser.coverage.extract_json import (
    build_json_section_texts,
    extract_json_all_texts,
    extract_json_paragraph_texts,
    extract_json_point_texts,
)


def _load_units_payload(payload: object, json_path: Path) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError(
            f"Unsupported JSON format in {json_path}: expected object root with key 'units'."
        )

    units = payload.get("units")
    if not isinstance(units, list):
        raise ValueError(
            f"Unsupported JSON format in {json_path}: key 'units' must be a list."
        )

    return units


def compare_counters(html_counter: Counter, json_counter: Counter) -> dict:
    """
    Compare two counters.

    Returns {missing, missing_raw, extra, matched}.
    """
    missing = []
    missing_raw = []
    extra = []
    matched = 0

    for text, count in html_counter.items():
        json_count = json_counter.get(text, 0)
        if json_count < count:
            for _ in range(count - json_count):
                missing.append(text[:100] + ("..." if len(text) > 100 else ""))
                missing_raw.append(text)
        matched += min(count, json_count)

    for text, count in json_counter.items():
        html_count = html_counter.get(text, 0)
        if count > html_count:
            for _ in range(count - html_count):
                extra.append(text[:100] + ("..." if len(text) > 100 else ""))

    return {"missing": missing, "missing_raw": missing_raw, "extra": extra, "matched": matched}


def coverage_test(html_path: Path, json_path: Path, oracle: str = "naive") -> dict:
    """Run coverage test comparing HTML and JSON."""
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    units = _load_units_payload(payload, json_path)

    is_consolidated = detect_format(soup)

    if oracle == "mirror":
        if is_consolidated:
            html_paragraphs = extract_paragraph_texts_consolidated(soup)
            html_points = extract_point_texts_consolidated(soup)
        else:
            html_paragraphs = extract_paragraph_texts_oj(soup)
            html_points = extract_point_texts_oj(soup)

        json_paragraphs = extract_json_paragraph_texts(units)
        json_points = extract_json_point_texts(units)
        json_all = extract_json_all_texts(units)
    else:
        html_paragraphs = {}
        html_points = {}
        json_paragraphs = {}
        json_points = {}

    report = {
        "format": "Consolidated" if is_consolidated else "OJ (Official Journal)",
        "paragraphs": {},
        "points": {},
        "summary": {},
        "oracle": oracle,
    }

    if oracle == "mirror":
        all_keys = set(html_paragraphs.keys()) | set(json_paragraphs.keys())
        total_html_par = 0
        total_missing_par = 0

        for key in sorted(all_keys, key=lambda x: (x != "recitals", int(x) if x.isdigit() else 999)):
            html_c = html_paragraphs.get(key, Counter())
            json_c = json_paragraphs.get(key, Counter())
            comparison = compare_counters(html_c, json_c)

            report["paragraphs"][key] = {
                "html_count": sum(html_c.values()),
                "json_count": sum(json_c.values()),
                "matched": comparison["matched"],
                "missing": comparison["missing"],
                "missing_raw": comparison["missing_raw"],
                "extra": comparison["extra"],
            }
            total_html_par += sum(html_c.values())
            total_missing_par += len(comparison["missing"])

        all_keys = set(html_points.keys()) | set(json_points.keys())
        total_html_pt = 0
        total_missing_pt = 0

        for key in sorted(all_keys, key=lambda x: int(x) if x.isdigit() else 999):
            html_c = html_points.get(key, Counter())
            json_c = json_points.get(key, Counter())
            comparison = compare_counters(html_c, json_c)

            report["points"][key] = {
                "html_count": sum(html_c.values()),
                "json_count": sum(json_c.values()),
                "matched": comparison["matched"],
                "missing": comparison["missing"],
                "missing_raw": comparison["missing_raw"],
                "extra": comparison["extra"],
            }
            total_html_pt += sum(html_c.values())
            total_missing_pt += len(comparison["missing"])

        total_gone = 0
        total_misclassified = 0

        for key, data in report["paragraphs"].items():
            gone_count = 0
            misclassified_count = 0
            all_c = json_all.get(key, Counter())
            for raw_text in data.get("missing_raw", []):
                if all_c.get(raw_text, 0) > 0:
                    misclassified_count += 1
                else:
                    gone_count += 1
            data["gone"] = gone_count
            data["misclassified"] = misclassified_count
            total_gone += gone_count
            total_misclassified += misclassified_count

        for key, data in report["points"].items():
            gone_count = 0
            misclassified_count = 0
            all_c = json_all.get(key, Counter())
            for raw_text in data.get("missing_raw", []):
                if all_c.get(raw_text, 0) > 0:
                    misclassified_count += 1
                else:
                    gone_count += 1
            data["gone"] = gone_count
            data["misclassified"] = misclassified_count
            total_gone += gone_count
            total_misclassified += misclassified_count

        total_html = total_html_par + total_html_pt
        total_missing = total_missing_par + total_missing_pt
        report["summary"] = {
            "total_html_segments": total_html,
            "total_missing": total_missing,
            "gone": total_gone,
            "misclassified": total_misclassified,
            "coverage_pct": 100.0 * (total_html - total_missing) / total_html if total_html > 0 else 100.0,
            "text_recall_pct": 100.0 * (total_html - total_gone) / total_html if total_html > 0 else 100.0,
        }
    else:
        naive_html = build_naive_section_map(soup)
        json_sections = build_json_section_texts(units)

        total_html = 0
        total_missing = 0
        for key in sorted(naive_html.keys()):
            html_segments = naive_html.get(key, [])
            json_texts = json_sections.get(key, [])
            missing = []
            for seg in html_segments:
                if not any(seg in jt for jt in json_texts):
                    missing.append(seg[:100] + ("..." if len(seg) > 100 else ""))

            report["paragraphs"][key] = {
                "html_count": len(html_segments),
                "json_count": len(json_texts),
                "matched": len(html_segments) - len(missing),
                "missing": missing,
                "extra": [],
            }
            total_html += len(html_segments)
            total_missing += len(missing)

        report["summary"] = {
            "total_html_segments": total_html,
            "total_missing": total_missing,
            "coverage_pct": 100.0 * (total_html - total_missing) / total_html if total_html > 0 else 100.0,
        }

    return report
