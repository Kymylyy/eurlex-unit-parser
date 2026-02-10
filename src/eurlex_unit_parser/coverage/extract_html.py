"""HTML extraction helpers used by coverage analysis."""

from __future__ import annotations

import re
from collections import Counter

from bs4 import BeautifulSoup, Tag

from eurlex_unit_parser.text_utils import get_cell_text, is_list_table, normalize_text, remove_note_tags, strip_leading_label

LABEL_ONLY_RE = re.compile(
    r"^(Article\s+\d+[A-Z]?|ANNEX\s+[IVXLC0-9]+|Part\s+[A-Z]|CHAPTER\s+[IVXLC0-9]+|SECTION\s+[IVXLC0-9]+|SUB-?SECTION\s+[IVXLC0-9]+|TITLE\s+[IVXLC0-9]+)(\s+[-—–:]\s+.*|\s+.*)?$",
    re.IGNORECASE,
)
PUNCT_LABEL_RE = re.compile(r"^\(?[a-zivx0-9]{1,4}\)?[.)]?$", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
LEADING_REF_RE = re.compile(r"^(?:['“”‘’]?\(?[a-zivx0-9]{1,4}\)?[.)]?)\s+", re.IGNORECASE)
LEADING_NUM_RE = re.compile(r"^(\d+)[.)]\s+")
LEADING_DASH_RE = re.compile(r"^[—–-]\s+")

NAIVE_HEADING_CLASSES = {
    "oj-ti-art",
    "oj-sti-art",
    "oj-doc-ti",
    "oj-ti-grseq-1",
    "oj-ti-grseq-2",
    "oj-ti-grseq-3",
    "oj-ti-grseq-4",
    "oj-ti-grseq-5",
    "oj-ti-grseq-6",
    "oj-ti-grseq-7",
    "oj-ti-grseq-8",
    "oj-ti-grseq-9",
    "oj-ti-grseq-10",
    "title-article-norm",
    "stitle-article-norm",
}


def detect_format(soup: BeautifulSoup) -> bool:
    """Detect if this is consolidated format."""
    if soup.find("p", class_="title-article-norm"):
        return True
    if soup.find("div", class_="grid-container"):
        return True
    return False


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def looks_like_label(line: str) -> bool:
    if not line:
        return True
    if LABEL_ONLY_RE.match(line.strip()):
        return True
    if PUNCT_LABEL_RE.match(line.strip()):
        return True
    return False


def strip_leading_ref(line: str) -> str:
    line = line.strip()
    while True:
        new_line = LEADING_NUM_RE.sub("", line)
        new_line = LEADING_REF_RE.sub("", new_line)
        new_line = LEADING_DASH_RE.sub("", new_line)
        if new_line == line:
            break
        line = new_line.strip()
    return line.strip()


def extract_naive_segments(container: Tag, min_len: int = 10) -> list[str]:
    clone = BeautifulSoup(str(container), "lxml")
    for cls in NAIVE_HEADING_CLASSES:
        for tag in clone.find_all(class_=cls):
            tag.decompose()

    raw = clone.get_text(separator="\n", strip=True)
    lines = [normalize_whitespace(line_text) for line_text in raw.splitlines()]
    segments = []
    for line in lines:
        line = strip_leading_ref(line)
        if len(line) < min_len:
            continue
        if looks_like_label(line):
            continue
        segments.append(line)
    return segments


def is_correlation_table_annex(div: Tag) -> bool:
    heading_texts = []
    for cls in list(NAIVE_HEADING_CLASSES) + ["oj-ti-tbl", "oj-doc-ti"]:
        for tag in div.find_all(class_=cls):
            heading_texts.append(tag.get_text(separator=" ", strip=True))
    for p in div.find_all("p", limit=5):
        heading_texts.append(p.get_text(separator=" ", strip=True))
    for text in heading_texts:
        if "correlation table" in text.lower():
            return True
    return False


def build_naive_section_map(soup: BeautifulSoup) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}

    for div in soup.find_all(
        "div",
        class_="eli-subdivision",
        id=lambda x: x and (x.startswith("rct_") or x.startswith("art_")),
    ):
        source_id = div.get("id", "")
        if source_id.startswith("rct_"):
            key = "recitals"
        else:
            article_num = source_id.replace("art_", "")
            key = f"art_{article_num}"
        sections.setdefault(key, []).extend(extract_naive_segments(div))

    for div in soup.find_all(
        "div", class_="eli-container", id=lambda x: x and x.strip().startswith("anx_")
    ):
        if is_correlation_table_annex(div):
            continue
        source_id = div.get("id", "").strip()
        annex_num = source_id.replace("anx_", "").strip()
        key = f"annex_{annex_num}" if annex_num else "annex"
        sections.setdefault(key, []).extend(extract_naive_segments(div))

    return sections


def get_consolidated_text_for_test(element: Tag) -> str:
    clone = BeautifulSoup(str(element), "lxml")
    root = clone.find("div") or clone.find("p") or clone

    for grid in root.find_all("div", class_="grid-container"):
        grid.decompose()

    texts = []
    for p in root.find_all("p", class_="norm"):
        text = p.get_text(separator=" ", strip=True)
        if text:
            texts.append(text)

    if texts:
        return " ".join(texts)

    return root.get_text(separator=" ", strip=True)


def extract_paragraph_texts_oj(soup: BeautifulSoup) -> dict[str, Counter]:
    result = {"recitals": Counter()}

    for div in soup.find_all("div", class_="eli-subdivision", id=lambda x: x and x.startswith("rct_")):
        table = div.find("table")
        if table and is_list_table(table):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    content_copy = BeautifulSoup(str(cells[1]), "lxml").find("td") or cells[1]
                    remove_note_tags(content_copy)
                    text = content_copy.get_text(separator=" ", strip=True)
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result["recitals"][text] += 1
        else:
            combined_parts = []
            for p in div.find_all("p", class_="oj-normal"):
                p_copy = BeautifulSoup(str(p), "lxml").find("p")
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=" ", strip=True)
                text, _ = strip_leading_label(text)
                if text:
                    combined_parts.append(text)

            full_text = normalize_text(" ".join(combined_parts))
            if full_text and len(full_text) > 5:
                result["recitals"][full_text] += 1

    for div in soup.find_all("div", class_="eli-subdivision", id=lambda x: x and x.startswith("art_")):
        article_num = div.get("id", "").replace("art_", "")
        result[article_num] = Counter()

        paragraph_divs = div.find_all("div", id=re.compile(r"^\d{3}\.\d{3}$"), recursive=False)

        if paragraph_divs:
            for par_div in paragraph_divs:
                for child in par_div.children:
                    if not isinstance(child, Tag):
                        continue
                    if child.name == "p" and "oj-normal" in child.get("class", []):
                        p_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                        remove_note_tags(p_copy)
                        text = p_copy.get_text(separator=" ", strip=True)
                        text, _ = strip_leading_label(text)
                        text = normalize_text(text)
                        if text and len(text) > 5:
                            result[article_num][text] += 1
        else:
            for p in div.find_all("p", class_="oj-normal", recursive=False):
                p_copy = BeautifulSoup(str(p), "lxml").find("p") or p
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=" ", strip=True)
                text, _ = strip_leading_label(text)
                text = normalize_text(text)
                if text and len(text) > 5:
                    result[article_num][text] += 1

    return result


def extract_point_texts_oj(soup: BeautifulSoup) -> dict[str, Counter]:
    result = {}

    for div in soup.find_all("div", class_="eli-subdivision", id=lambda x: x and x.startswith("art_")):
        article_num = div.get("id", "").replace("art_", "")
        result[article_num] = Counter()

        for table in div.find_all("table"):
            if table.find_parent("td"):
                continue
            if not is_list_table(table):
                continue

            tbody = table.find("tbody", recursive=False)
            rows = tbody.find_all("tr", recursive=False) if tbody else table.find_all("tr", recursive=False)

            for row in rows:
                cells = row.find_all("td", recursive=False)
                if len(cells) >= 2:
                    text = get_cell_text(cells[1], exclude_nested_tables=True)
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result[article_num][text] += 1

    return result


def extract_paragraph_texts_consolidated(soup: BeautifulSoup) -> dict[str, Counter]:
    result = {}

    for div in soup.find_all("div", class_="eli-subdivision", id=lambda x: x and x.startswith("art_")):
        article_num = div.get("id", "").replace("art_", "")
        result[article_num] = Counter()

        for child in div.children:
            if not isinstance(child, Tag):
                continue

            if "eli-title" in child.get("class", []):
                continue
            if child.name == "p" and any(
                c in child.get("class", []) for c in ["title-article-norm", "stitle-article-norm"]
            ):
                continue

            if child.name == "div" and "norm" in child.get("class", []):
                no_parag = child.find("span", class_="no-parag", recursive=False)
                if no_parag:
                    inline_div = child.find("div", class_="inline-element", recursive=False)
                    if inline_div:
                        text = get_consolidated_text_for_test(inline_div)
                    else:
                        text = child.get_text(separator=" ", strip=True)
                        text = text.replace(no_parag.get_text(), "", 1).strip()
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result[article_num][text] += 1

            elif child.name == "p" and "norm" in child.get("class", []):
                text = child.get_text(separator=" ", strip=True)
                text = normalize_text(text)
                if text and len(text) > 5:
                    result[article_num][text] += 1

    return result


def extract_point_texts_consolidated(soup: BeautifulSoup) -> dict[str, Counter]:
    result = {}

    for div in soup.find_all("div", class_="eli-subdivision", id=lambda x: x and x.startswith("art_")):
        article_num = div.get("id", "").replace("art_", "")
        result[article_num] = Counter()

        for grid in div.find_all("div", class_="grid-container"):
            content_div = grid.find("div", class_="grid-list-column-2")
            if content_div:
                for p in content_div.find_all("p", class_="norm", recursive=False):
                    text = p.get_text(separator=" ", strip=True)
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result[article_num][text] += 1

    return result


def build_full_html_text_by_section(soup: BeautifulSoup) -> dict[str, str]:
    sections: dict[str, str] = {}

    for div in soup.find_all(
        "div",
        class_="eli-subdivision",
        id=lambda x: x and (x.startswith("rct_") or x.startswith("art_")),
    ):
        source_id = div.get("id", "")
        if source_id.startswith("rct_"):
            key = "recitals"
        else:
            article_num = source_id.replace("art_", "")
            key = f"art_{article_num}"
        clone = BeautifulSoup(str(div), "lxml")
        root = clone.find("div") or clone
        remove_note_tags(root)
        text = normalize_text(root.get_text(separator=" ", strip=True))
        if key in sections:
            sections[key] = f"{sections[key]} {text}".strip()
        else:
            sections[key] = text

    for div in soup.find_all("div", class_="eli-container", id=lambda x: x and x.strip().startswith("anx_")):
        source_id = div.get("id", "").strip()
        annex_num = source_id.replace("anx_", "").strip()
        key = f"annex_{annex_num}" if annex_num else "annex"
        clone = BeautifulSoup(str(div), "lxml")
        root = clone.find("div") or clone
        remove_note_tags(root)
        text = normalize_text(root.get_text(separator=" ", strip=True))
        if key in sections:
            sections[key] = f"{sections[key]} {text}".strip()
        else:
            sections[key] = text

    return sections
