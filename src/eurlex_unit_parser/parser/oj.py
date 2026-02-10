"""Official Journal (OJ) parsing flow."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from eurlex_unit_parser.models import Unit
from eurlex_unit_parser.text_utils import (
    is_list_table,
    get_cell_text,
    normalize_text,
    remove_note_tags,
    strip_leading_label,
)


class OJParserMixin:
    """Mixin implementing parser logic for OJ-format EUR-Lex pages."""

    def _parse_document_title(self) -> None:
        title_div = self.soup.find("div", class_="eli-main-title")
        if not title_div:
            title_div = self.soup.find("div", id=lambda x: x and x.startswith("tit_"))
        if not title_div:
            return

        title_parts = []
        title_paragraphs = title_div.find_all("p", class_="oj-doc-ti")
        if not title_paragraphs:
            title_paragraphs = title_div.find_all("p")

        for p in title_paragraphs:
            p_copy = BeautifulSoup(str(p), "lxml").find("p") or p
            remove_note_tags(p_copy)
            text = normalize_text(p_copy.get_text(separator=" ", strip=True))
            if not text:
                continue
            if re.match(r"^\(\s*Text with .* relevance\s*\)$", text, re.IGNORECASE):
                continue
            title_parts.append(text)

        if not title_parts:
            return

        self._add_unit(
            Unit(
                id="document-title",
                type="document_title",
                ref=None,
                text=" ".join(title_parts),
                parent_id=None,
                source_id=title_div.get("id", ""),
                source_file=self.source_file,
            )
        )

    def _parse_recitals(self) -> None:
        recital_divs = self.soup.find_all(
            "div", class_="eli-subdivision", id=lambda x: x and x.startswith("rct_")
        )

        for div in recital_divs:
            source_id = div.get("id", "")
            recital_num = source_id.replace("rct_", "")

            table = div.find("table")
            if table and is_list_table(table):
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label_text = get_cell_text(cells[0]).strip()
                        content_text = get_cell_text(cells[1])

                        m = re.match(r"\((\d+)\)", label_text)
                        if m:
                            recital_num = m.group(1)

                        unit = Unit(
                            id=f"recital-{recital_num}",
                            type="recital",
                            ref=label_text,
                            text=normalize_text(content_text),
                            parent_id=None,
                            source_id=source_id,
                            source_file=self.source_file,
                            recital_number=recital_num,
                        )
                        self._add_unit(unit)
            else:
                p_elements = div.find_all("p", class_="oj-normal")
                if p_elements:
                    combined_parts = []
                    for p in p_elements:
                        p_copy = BeautifulSoup(str(p), "lxml").find("p")
                        remove_note_tags(p_copy)
                        p_text = p_copy.get_text(separator=" ", strip=True)
                        p_text, _ = strip_leading_label(p_text)
                        if p_text:
                            combined_parts.append(p_text)
                    text = " ".join(combined_parts)
                    unit = Unit(
                        id=f"recital-{recital_num}",
                        type="recital",
                        ref=f"({recital_num})",
                        text=normalize_text(text),
                        parent_id=None,
                        source_id=source_id,
                        source_file=self.source_file,
                        recital_number=recital_num,
                    )
                    self._add_unit(unit)

    def _parse_articles(self) -> None:
        article_divs = self.soup.find_all(
            "div", class_="eli-subdivision", id=lambda x: x and x.startswith("art_")
        )

        for div in article_divs:
            source_id = div.get("id", "")
            article_num = source_id.replace("art_", "")

            title_p = div.find("p", class_="oj-ti-art")
            _article_title = title_p.get_text(strip=True) if title_p else f"Article {article_num}"

            subtitle = None
            subtitle_div = div.find("div", class_="eli-title")
            if subtitle_div:
                subtitle_p = subtitle_div.find("p", class_="oj-sti-art")
                if subtitle_p:
                    subtitle = subtitle_p.get_text(strip=True)

            article_id = f"art-{article_num}"
            article_unit = Unit(
                id=article_id,
                type="article",
                ref=f"Article {article_num}",
                text="",
                parent_id=None,
                source_id=source_id,
                source_file=self.source_file,
                article_number=article_num,
                heading=subtitle,
            )
            self._add_unit(article_unit)

            is_amending = False
            if subtitle and re.search(r"Amendments?\s+to\b|Amendment\s+of\b", subtitle, re.IGNORECASE):
                is_amending = True
            if not is_amending:
                first_p = div.find("p", class_="oj-normal")
                if first_p:
                    ft = first_p.get_text(strip=True)[:200]
                    if "is amended as follows" in ft or "are amended as follows" in ft:
                        is_amending = True

            if is_amending:
                self._parse_amending_article(div, article_id, article_num)
                continue

            paragraph_divs = div.find_all("div", id=re.compile(r"^\d{3}\.\d{3}$"), recursive=False)

            if paragraph_divs:
                self._parse_paragraphs(paragraph_divs, article_id, article_num)
            else:
                self._parse_article_direct_content(div, article_id, article_num)

    def _parse_paragraphs(self, paragraph_divs: list[Tag], article_id: str, article_num: str) -> None:
        for idx, par_div in enumerate(paragraph_divs):
            par_source_id = par_div.get("id", "")
            par_num = None
            par_id = None
            current_parent = None
            subpar_idx = 0
            pending_tables: list[Tag] = []

            for child in par_div.children:
                if not isinstance(child, Tag):
                    if isinstance(child, NavigableString) and par_id is not None:
                        bare = child.strip()
                        if bare and len(bare) >= 10:
                            subpar_idx += 1
                            subpar_id = f"{par_id}.subpar-{subpar_idx}"
                            self._add_unit(
                                Unit(
                                    id=subpar_id,
                                    type="subparagraph",
                                    ref=None,
                                    text=normalize_text(bare),
                                    parent_id=par_id,
                                    source_id="",
                                    source_file=self.source_file,
                                    article_number=article_num,
                                    paragraph_number=par_num,
                                )
                            )
                            current_parent = subpar_id
                    continue

                if child.name == "p" and (
                    "oj-normal" in child.get("class", [])
                    or "oj-ti-tbl" in child.get("class", [])
                    or "oj-note" in child.get("class", [])
                ):
                    if pending_tables and current_parent:
                        self._parse_point_tables(pending_tables, current_parent, article_num, par_num)
                        pending_tables = []

                    p_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                    remove_note_tags(p_copy)
                    text = p_copy.get_text(separator=" ", strip=True)

                    if par_id is None:
                        text_content, par_num = strip_leading_label(text)
                        par_id = f"{article_id}.par-{par_num}" if par_num else f"{article_id}.par-{idx + 1}"

                        par_unit = Unit(
                            id=par_id,
                            type="paragraph",
                            ref=f"{par_num}." if par_num else None,
                            text=normalize_text(text_content),
                            parent_id=article_id,
                            source_id=par_source_id,
                            source_file=self.source_file,
                            article_number=article_num,
                            paragraph_number=par_num,
                            paragraph_index=idx + 1 if not par_num else None,
                        )
                        self._add_unit(par_unit)
                        current_parent = par_id
                    else:
                        subpar_idx += 1
                        subpar_id = f"{par_id}.subpar-{subpar_idx}"

                        subpar_unit = Unit(
                            id=subpar_id,
                            type="subparagraph",
                            ref=None,
                            text=normalize_text(text),
                            parent_id=par_id,
                            source_id=child.get("id", ""),
                            source_file=self.source_file,
                            article_number=article_num,
                            paragraph_number=par_num,
                        )
                        self._add_unit(subpar_unit)
                        current_parent = subpar_id

                elif child.name == "table":
                    pending_tables.append(child)

                elif child.name == "div":
                    child_id = child.get("id", "")
                    child_classes = child.get("class", [])
                    if not child_id and "eli-subdivision" not in child_classes and "eli-title" not in child_classes:
                        for p in child.find_all("p", class_="oj-normal", recursive=False):
                            if pending_tables and current_parent:
                                self._parse_point_tables(pending_tables, current_parent, article_num, par_num)
                                pending_tables = []

                            p_copy = BeautifulSoup(str(p), "lxml").find("p") or p
                            remove_note_tags(p_copy)
                            text = p_copy.get_text(separator=" ", strip=True)

                            if par_id is None:
                                text_content, par_num = strip_leading_label(text)
                                par_id = f"{article_id}.par-{par_num}" if par_num else f"{article_id}.par-{idx + 1}"
                                self._add_unit(
                                    Unit(
                                        id=par_id,
                                        type="paragraph",
                                        ref=f"{par_num}." if par_num else None,
                                        text=normalize_text(text_content),
                                        parent_id=article_id,
                                        source_id=par_source_id,
                                        source_file=self.source_file,
                                        article_number=article_num,
                                        paragraph_number=par_num,
                                        paragraph_index=idx + 1 if not par_num else None,
                                    )
                                )
                                current_parent = par_id
                            else:
                                subpar_idx += 1
                                subpar_id = f"{par_id}.subpar-{subpar_idx}"
                                self._add_unit(
                                    Unit(
                                        id=subpar_id,
                                        type="subparagraph",
                                        ref=None,
                                        text=normalize_text(text),
                                        parent_id=par_id,
                                        source_id=p.get("id", ""),
                                        source_file=self.source_file,
                                        article_number=article_num,
                                        paragraph_number=par_num,
                                    )
                                )
                                current_parent = subpar_id

            if pending_tables:
                if current_parent is None:
                    m = re.search(r"\.(\d+)", par_source_id)
                    par_num = str(int(m.group(1))) if m else str(idx + 1)
                    par_id = f"{article_id}.par-{par_num}"
                    self._add_unit(
                        Unit(
                            id=par_id,
                            type="paragraph",
                            ref=f"{par_num}.",
                            text="",
                            parent_id=article_id,
                            source_id=par_source_id,
                            source_file=self.source_file,
                            article_number=article_num,
                            paragraph_number=par_num,
                        )
                    )
                    current_parent = par_id
                self._parse_point_tables(pending_tables, current_parent, article_num, par_num)

    def _parse_article_direct_content(self, article_div: Tag, article_id: str, article_num: str) -> None:
        title_div = article_div.find("div", class_="eli-title")

        par_id = None
        current_parent = None
        subpar_idx = 0
        pending_tables: list[Tag] = []

        for child in article_div.children:
            if not isinstance(child, Tag):
                continue

            if child == title_div:
                continue
            if child.name == "p" and "oj-ti-art" in child.get("class", []):
                continue
            if child.name == "p" and "oj-sti-art" in child.get("class", []):
                continue

            if child.name == "p" and (
                "oj-normal" in child.get("class", [])
                or "oj-ti-tbl" in child.get("class", [])
                or "oj-note" in child.get("class", [])
            ):
                if pending_tables and current_parent:
                    self._parse_point_tables(
                        pending_tables,
                        current_parent,
                        article_num,
                        None,
                        is_direct=True,
                    )
                    pending_tables = []

                p_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=" ", strip=True)

                if par_id is None:
                    par_id = f"{article_id}.par-1"
                    par_unit = Unit(
                        id=par_id,
                        type="paragraph",
                        ref=None,
                        text=normalize_text(text),
                        parent_id=article_id,
                        source_id=child.get("id", ""),
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=None,
                        paragraph_index=1,
                    )
                    self._add_unit(par_unit)
                    current_parent = par_id
                else:
                    subpar_idx += 1
                    subpar_id = f"{par_id}.subpar-{subpar_idx}"

                    subpar_unit = Unit(
                        id=subpar_id,
                        type="subparagraph",
                        ref=None,
                        text=normalize_text(text),
                        parent_id=par_id,
                        source_id=child.get("id", ""),
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=None,
                    )
                    self._add_unit(subpar_unit)
                    current_parent = subpar_id

            elif child.name == "table":
                pending_tables.append(child)

            elif child.name == "div" and child != title_div:
                child_id = child.get("id", "")
                child_classes = child.get("class", [])
                if not child_id and "eli-subdivision" not in child_classes and "eli-title" not in child_classes:
                    for p in child.find_all("p", class_="oj-normal", recursive=False):
                        if pending_tables and current_parent:
                            self._parse_point_tables(
                                pending_tables,
                                current_parent,
                                article_num,
                                None,
                                is_direct=True,
                            )
                            pending_tables = []

                        p_copy = BeautifulSoup(str(p), "lxml").find("p") or p
                        remove_note_tags(p_copy)
                        text = p_copy.get_text(separator=" ", strip=True)

                        if par_id is None:
                            par_id = f"{article_id}.par-1"
                            self._add_unit(
                                Unit(
                                    id=par_id,
                                    type="paragraph",
                                    ref=None,
                                    text=normalize_text(text),
                                    parent_id=article_id,
                                    source_id=p.get("id", ""),
                                    source_file=self.source_file,
                                    article_number=article_num,
                                    paragraph_number=None,
                                    paragraph_index=1,
                                )
                            )
                            current_parent = par_id
                        else:
                            subpar_idx += 1
                            subpar_id = f"{par_id}.subpar-{subpar_idx}"
                            self._add_unit(
                                Unit(
                                    id=subpar_id,
                                    type="subparagraph",
                                    ref=None,
                                    text=normalize_text(text),
                                    parent_id=par_id,
                                    source_id=p.get("id", ""),
                                    source_file=self.source_file,
                                    article_number=article_num,
                                    paragraph_number=None,
                                )
                            )
                            current_parent = subpar_id

        if pending_tables and current_parent:
            self._parse_point_tables(pending_tables, current_parent, article_num, None, is_direct=True)

    def _parse_amending_article(self, article_div: Tag, article_id: str, article_num: str) -> None:
        skip_classes = {"oj-ti-art", "oj-sti-art", "oj-doc-ti"}
        par_id = f"{article_id}.par-1"
        par_created = False
        subpar_idx = 0
        seen_texts: set[str] = set()
        first_p = True

        def ensure_paragraph() -> None:
            nonlocal par_created
            if not par_created:
                self._add_unit(
                    Unit(
                        id=par_id,
                        type="paragraph",
                        ref=None,
                        text="",
                        parent_id=article_id,
                        source_id="",
                        source_file=self.source_file,
                        article_number=article_num,
                        is_amendment_text=True,
                    )
                )
                par_created = True

        def walk(container: Tag) -> None:
            nonlocal subpar_idx, first_p, par_created

            for child in container.children:
                if isinstance(child, NavigableString):
                    text = child.strip()
                    if text and len(text) >= 10:
                        text = normalize_text(text)
                        if text not in seen_texts:
                            seen_texts.add(text)
                            ensure_paragraph()
                            subpar_idx += 1
                            self._add_unit(
                                Unit(
                                    id=f"{par_id}.subpar-{subpar_idx}",
                                    type="subparagraph",
                                    ref=None,
                                    text=text,
                                    parent_id=par_id,
                                    source_id="",
                                    source_file=self.source_file,
                                    article_number=article_num,
                                    is_amendment_text=True,
                                )
                            )
                    continue

                if not isinstance(child, Tag):
                    continue

                if child.name == "p":
                    classes = set(child.get("class", []))
                    if "oj-note" in classes:
                        continue
                    if classes & skip_classes:
                        continue
                    p_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                    remove_note_tags(p_copy)
                    text = p_copy.get_text(separator=" ", strip=True)
                    if not text or len(text.strip()) < 3:
                        continue
                    text, label = strip_leading_label(text)
                    text = normalize_text(text)
                    if text in seen_texts:
                        continue
                    seen_texts.add(text)

                    if first_p and not par_created:
                        self._add_unit(
                            Unit(
                                id=par_id,
                                type="paragraph",
                                ref=f"{label}." if label else None,
                                text=text,
                                parent_id=article_id,
                                source_id="",
                                source_file=self.source_file,
                                article_number=article_num,
                                is_amendment_text=True,
                            )
                        )
                        par_created = True
                        first_p = False
                    else:
                        ensure_paragraph()
                        subpar_idx += 1
                        self._add_unit(
                            Unit(
                                id=f"{par_id}.subpar-{subpar_idx}",
                                type="subparagraph",
                                ref=None,
                                text=text,
                                parent_id=par_id,
                                source_id="",
                                source_file=self.source_file,
                                article_number=article_num,
                                is_amendment_text=True,
                            )
                        )
                        first_p = False

                elif child.name == "table":
                    ensure_paragraph()
                    if is_list_table(child):
                        self._parse_point_tables(
                            [child],
                            par_id,
                            article_num,
                            paragraph_num=None,
                            depth=0,
                            is_amendment=True,
                        )
                    else:
                        self._extract_non_list_table_content(
                            child,
                            par_id,
                            article_num,
                            paragraph_num=None,
                            is_amendment=True,
                        )

                elif child.name == "div":
                    walk(child)

                elif child.name == "figure":
                    continue

                else:
                    text = child.get_text(separator=" ", strip=True)
                    if text and len(text) >= 10:
                        text = normalize_text(text)
                        if text not in seen_texts:
                            seen_texts.add(text)
                            ensure_paragraph()
                            subpar_idx += 1
                            self._add_unit(
                                Unit(
                                    id=f"{par_id}.unk-{subpar_idx}",
                                    type="unknown_unit",
                                    ref=None,
                                    text=text,
                                    parent_id=par_id,
                                    source_id="",
                                    source_file=self.source_file,
                                    article_number=article_num,
                                    is_amendment_text=True,
                                )
                            )

        walk(article_div)
