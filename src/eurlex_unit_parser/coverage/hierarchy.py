"""Hierarchy and ordering validation for parsed units."""

from __future__ import annotations


def validate_hierarchy(units: list[dict]) -> dict:
    """Validate hierarchy structure of parsed units."""
    issues = []

    all_ids = {u["id"] for u in units}
    units_by_id = {u["id"]: u for u in units}

    parent_type_rules = {
        "subparagraph": ["paragraph"],
        "point": ["paragraph", "subparagraph", "article"],
        "subpoint": ["point", "annex_item"],
        "subsubpoint": ["subpoint"],
    }

    for unit in units:
        unit_id = unit["id"]
        unit_type = unit["type"]
        parent_id = unit.get("parent_id")

        if parent_id and parent_id not in all_ids:
            issues.append(
                {
                    "type": "orphan",
                    "id": unit_id,
                    "message": f"parent_id '{parent_id}' does not exist",
                }
            )

        if parent_id and unit_type in parent_type_rules:
            parent = units_by_id.get(parent_id)
            if parent:
                expected_types = parent_type_rules[unit_type]
                if parent["type"] not in expected_types:
                    issues.append(
                        {
                            "type": "wrong_parent_type",
                            "id": unit_id,
                            "message": f"{unit_type} has parent type '{parent['type']}', expected one of {expected_types}",
                        }
                    )

        if unit_type == "paragraph" and unit.get("paragraph_number"):
            expected_suffix = f".par-{unit['paragraph_number']}"
            if expected_suffix not in unit_id:
                issues.append(
                    {
                        "type": "id_mismatch",
                        "id": unit_id,
                        "message": f"paragraph_number={unit['paragraph_number']} doesn't match id",
                    }
                )

        if unit_type == "point" and unit.get("point_label"):
            expected_suffix = f".pt-{unit['point_label']}"
            if expected_suffix not in unit_id:
                issues.append(
                    {
                        "type": "id_mismatch",
                        "id": unit_id,
                        "message": f"point_label={unit['point_label']} doesn't match id",
                    }
                )

    return {"valid": len(issues) == 0, "issues": issues}


def validate_ordering(units: list[dict]) -> dict:
    """Validate that points and subparagraphs are not interleaved under the same parent."""
    issues = []

    children_by_parent: dict[str, list[dict]] = {}
    for u in units:
        pid = u.get("parent_id", "")
        if pid:
            children_by_parent.setdefault(pid, []).append(u)

    for _pid, kids in children_by_parent.items():
        types = [u["type"] for u in kids]
        if "point" not in types or "subparagraph" not in types:
            continue

        state = "start"
        for _i, t in enumerate(types):
            if state == "start":
                if t == "point":
                    state = "points"
                elif t == "subparagraph":
                    state = "intro_subpar"
            elif state == "intro_subpar":
                if t == "point":
                    state = "points"
            elif state == "points":
                if t == "subparagraph":
                    state = "gap_subpar"
            elif state == "gap_subpar":
                if t == "point":
                    state = "points"
                elif t != "subparagraph":
                    state = "start"

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }
