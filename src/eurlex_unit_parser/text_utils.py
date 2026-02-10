"""Text and HTML utility helpers shared across parser and coverage tooling."""

import re
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from eurlex_unit_parser.labels import normalize_label


def is_list_table(table: Tag) -> bool:
    """Heuristic to determine if a table is a list-table (2 columns, label on left)."""
    cols = table.find_all("col", recursive=False)
    if not cols:
        colgroup = table.find("colgroup", recursive=False)
        if colgroup:
            cols = colgroup.find_all("col", recursive=False)
    has_cols = len(cols) == 2

    if has_cols:
        first_col = cols[0]
        width = first_col.get("width", "")
        if "%" in width:
            try:
                pct = int(width.replace("%", ""))
                if pct > 15:
                    return False
            except ValueError:
                pass

    tbody = table.find("tbody", recursive=False)
    first_row = tbody.find("tr", recursive=False) if tbody else table.find("tr", recursive=False)

    if first_row:
        tds = first_row.find_all("td", recursive=False)
        if not has_cols and len(tds) != 2:
            return False
        first_td = tds[0] if tds else None
        if first_td:
            p_elem = first_td.find("p", recursive=False)
            text = p_elem.get_text(strip=True) if p_elem else first_td.get_text(strip=True)
            if len(text) <= 15:
                _, label_type, _ = normalize_label(text)
                if label_type != "unknown":
                    return True

    return False


def remove_note_tags(element: Tag) -> None:
    """Remove footnote anchors and superscript note tags from element."""
    for a in element.find_all("a", href=True):
        href = a.get("href", "")
        if "#ntr" in href or "#ntc" in href:
            a.decompose()
            continue
        classes = a.get("class", []) or []
        if any("note" in c for c in classes):
            a.decompose()

    for span in element.find_all("span", class_="oj-note-tag"):
        span.decompose()
    for span in element.find_all("span", class_="oj-super"):
        text = span.get_text(strip=True)
        if re.match(r"^[*]?\d+$", text):
            span.decompose()


def get_cell_text(cell: Tag, exclude_nested_tables: bool = False) -> str:
    """
    Extract text from a table cell, optionally excluding nested tables.
    When exclude_nested_tables=True, only returns text from <p> elements
    that appear before the first nested <table>.
    """
    cell_copy = BeautifulSoup(str(cell), "lxml").find("td") or cell
    remove_note_tags(cell_copy)

    if exclude_nested_tables:
        has_nested = bool(cell_copy.find("table", recursive=False) or cell_copy.find("div", recursive=False))
        texts = []
        for child in cell_copy.children:
            if isinstance(child, NavigableString):
                t = child.strip()
                if t:
                    texts.append(t)
                continue
            if not isinstance(child, Tag):
                continue
            if child.name == "table":
                break
            if child.name == "p":
                if "oj-note" in child.get("class", []):
                    continue
                text = child.get_text(separator=" ", strip=True)
                if text:
                    texts.append(text)
                    if has_nested:
                        break
        if texts:
            return " ".join(texts)
        for nested_table in cell_copy.find_all("table"):
            nested_table.decompose()
        return cell_copy.get_text(separator=" ", strip=True)

    paragraphs = cell_copy.find_all("p", recursive=False)
    if paragraphs:
        texts = [p.get_text(separator=" ", strip=True) for p in paragraphs if p.get_text(strip=True)]
        return " ".join(texts)

    return cell_copy.get_text(separator=" ", strip=True)


def normalize_text(text: str) -> str:
    """Normalize whitespace and trim."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_leading_label(text: str) -> tuple[str, Optional[str]]:
    """Strip leading label from text and return (text_without_label, label)."""
    m = re.match(r"^(\d+)\.\s+(.*)$", text, re.DOTALL)
    if m:
        return m.group(2).strip(), m.group(1)
    return text, None
