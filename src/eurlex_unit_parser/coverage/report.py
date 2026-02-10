"""Coverage report printer."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional


def print_report(
    report: dict,
    hierarchy: dict,
    verbose: bool = False,
    phantom: Optional[Mapping[str, Any]] = None,
    ordering: Optional[Mapping[str, Any]] = None,
) -> bool:
    """Print coverage report. Returns True if all passed."""
    print(f"\n{'=' * 60}")
    print("COVERAGE REPORT")
    print(f"{'=' * 60}")
    print(f"Format: {report['format']}")

    print(f"\nORACLE: {report.get('oracle', 'mirror')}")

    print("\nSECTIONS:")
    par_issues = []
    for key, data in report["paragraphs"].items():
        if data["missing"]:
            par_issues.append((key, data))
        elif verbose:
            label = "Recitals" if key == "recitals" else key
            print(f"  [OK] {label}: {data['json_count']}/{data['html_count']}")

    if par_issues:
        for key, data in par_issues:
            label = "Recitals" if key == "recitals" else key
            print(f"  [!!] {label}: {data['json_count']}/{data['html_count']} ({len(data['missing'])} missing)")
            if verbose:
                for m in data["missing"][:3]:
                    print(f"       - {m}")
    else:
        print(f"  [OK] All {len(report['paragraphs'])} sections fully covered")

    if report.get("oracle") == "mirror" and report["points"]:
        print("\nPOINTS:")
        pt_issues = []
        for key, data in report["points"].items():
            if data["missing"]:
                pt_issues.append((key, data))

        if pt_issues:
            for key, data in pt_issues:
                print(
                    f"  [!!] Article {key}: {data['json_count']}/{data['html_count']} ({len(data['missing'])} missing)"
                )
                if verbose:
                    for m in data["missing"][:3]:
                        print(f"       - {m}")
        else:
            total_points = sum(d["json_count"] for d in report["points"].values())
            print(f"  [OK] All {total_points} points covered")

    print("\nHIERARCHY:")
    if hierarchy["valid"]:
        print("  [OK] All parent_ids valid")
        print("  [OK] ID/metadata consistent")
    else:
        for issue in hierarchy["issues"][:5]:
            print(f"  [!!] {issue['type']}: {issue['id']}")
            print(f"       {issue['message']}")
        if len(hierarchy["issues"]) > 5:
            print(f"  ... and {len(hierarchy['issues']) - 5} more issues")

    print("\nORDERING:")
    if ordering is None or ordering["valid"]:
        print("  [OK] No interleaved points/subparagraphs")
    else:
        for issue in ordering["issues"][:5]:
            print(f"  [!!] {issue['type']}: parent={issue['parent_id']}")
            print(f"       {issue['message']}")
        if len(ordering["issues"]) > 5:
            print(f"  ... and {len(ordering['issues']) - 5} more issues")

    print(f"\n{'=' * 60}")
    coverage = report["summary"]["coverage_pct"]
    text_recall = report["summary"].get("text_recall_pct", coverage)
    gone = report["summary"].get("gone", report["summary"]["total_missing"])
    misclassified = report["summary"].get("misclassified", 0)
    phantom_count = 0
    if phantom:
        phantom_count = phantom.get("total", 0)
    ordering_ok = ordering is None or ordering["valid"]
    ordering_count = 0 if ordering is None else len(ordering["issues"])
    status = "PASS" if gone == 0 and hierarchy["valid"] and phantom_count == 0 and ordering_ok else "ISSUES"
    print(f"SUMMARY: {text_recall:.1f}% text recall ({coverage:.1f}% strict) - {status}")
    print(f"  Total HTML segments: {report['summary']['total_html_segments']}")
    print(f"  Gone (truly missing): {gone}")
    print(f"  Misclassified: {misclassified}")
    print(f"  Hierarchy issues: {len(hierarchy['issues'])}")
    print(f"  Ordering issues: {ordering_count}")
    if phantom is not None:
        print(f"  Phantom segments: {phantom_count}")
    print(f"{'=' * 60}")

    metrics = {
        "coverage_pct": round(coverage, 1),
        "text_recall_pct": round(text_recall, 1),
        "gone": gone,
        "misclassified": misclassified,
        "total_html": report["summary"]["total_html_segments"],
        "total_missing": report["summary"]["total_missing"],
        "phantom": phantom_count,
        "hierarchy_ok": hierarchy["valid"],
        "ordering_ok": ordering_ok,
    }
    print(f"METRICS_JSON: {json.dumps(metrics)}")

    return gone == 0 and hierarchy["valid"] and phantom_count == 0 and ordering_ok
