"""Annex parsing logic."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from eurlex_unit_parser.labels import normalize_label
from eurlex_unit_parser.models import Unit
from eurlex_unit_parser.text_utils import get_cell_text, is_list_table, normalize_text, remove_note_tags


class AnnexParserMixin:
    """Mixin implementing annex parsing and annex item extraction."""

    def _parse_annexes(self) -> None:
        annex_divs = self.soup.find_all(
            "div", class_="eli-container", id=lambda x: x and x.strip().startswith("anx_")
        )

        for div in annex_divs:
            source_id = div.get("id", "").strip()
            annex_num = source_id.replace("anx_", "").strip()

            title_p = div.find("p", class_="oj-doc-ti")
            if title_p:
                title_copy = BeautifulSoup(str(title_p), "lxml").find("p") or title_p
                remove_note_tags(title_copy)
                annex_title = normalize_text(title_copy.get_text(separator=" ", strip=True))
            else:
                annex_title = f"ANNEX {annex_num}"

            heading_p = div.find("p", class_="oj-ti-grseq-1")
            heading = None
            if heading_p:
                heading_copy = BeautifulSoup(str(heading_p), "lxml").find("p") or heading_p
                remove_note_tags(heading_copy)
                heading = normalize_text(heading_copy.get_text(separator=" ", strip=True))

            annex_id = f"annex-{annex_num}"
            annex_unit = Unit(
                id=annex_id,
                type="annex",
                ref=f"ANNEX {annex_num}",
                text="",
                parent_id=None,
                source_id=source_id,
                source_file=self.source_file,
                annex_number=annex_num,
                heading=heading or annex_title,
            )
            self._add_unit(annex_unit)

            self._parse_annex_content(div, annex_id, annex_num)

    def _parse_annex_content(self, annex_div: Tag, annex_id: str, annex_num: str) -> None:
        current_part = None
        current_parent_id = annex_id
        annex_item_idx = 0

        for child in annex_div.children:
            if not isinstance(child, Tag):
                continue

            if child.name == "p" and "oj-ti-grseq-1" in child.get("class", []):
                child_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                remove_note_tags(child_copy)
                text = normalize_text(child_copy.get_text(separator=" ", strip=True))
                if text.lower().startswith("part "):
                    m = re.match(r"Part\s+([A-Z])", text, re.IGNORECASE)
                    if m:
                        current_part = m.group(1).upper()
                        part_id = f"{annex_id}.part-{current_part}"
                        part_unit = Unit(
                            id=part_id,
                            type="annex_part",
                            ref=f"Part {current_part}",
                            text=text,
                            parent_id=annex_id,
                            source_id="",
                            source_file=self.source_file,
                            annex_number=annex_num,
                            annex_part=current_part,
                        )
                        self._add_unit(part_unit)
                        current_parent_id = part_id

            elif child.name == "table" and is_list_table(child):
                rows = child.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label_text = get_cell_text(cells[0]).strip()
                        content_text = get_cell_text(cells[1], exclude_nested_tables=True)

                        label_normalized, _label_type, is_quoted = normalize_label(label_text)

                        item_id = f"{current_parent_id}.item-{label_normalized}"
                        item_unit = Unit(
                            id=item_id,
                            type="annex_item",
                            ref=label_text,
                            text=normalize_text(content_text),
                            parent_id=current_parent_id,
                            source_id="",
                            source_file=self.source_file,
                            annex_number=annex_num,
                            annex_part=current_part,
                            is_amendment_text=is_quoted,
                        )
                        self._add_unit(item_unit)

                        nested_tables = cells[1].find_all("table", recursive=False)
                        if nested_tables:
                            self._parse_point_tables(nested_tables, item_id, None, None, depth=1)

            elif child.name == "table" and not is_list_table(child):
                for row in child.find_all("tr"):
                    for cell in row.find_all(["td", "th"]):
                        cell_copy = BeautifulSoup(str(cell), "lxml").find(["td", "th"]) or cell
                        remove_note_tags(cell_copy)
                        direct_paragraphs = cell_copy.find_all("p", recursive=False)
                        if direct_paragraphs:
                            for p in direct_paragraphs:
                                t = p.get_text(separator=" ", strip=True)
                                if t and len(t.strip()) >= 5:
                                    annex_item_idx += 1
                                    self._add_unit(
                                        Unit(
                                            id=f"{current_parent_id}.item-{annex_item_idx}",
                                            type="annex_item",
                                            ref=None,
                                            text=normalize_text(t),
                                            parent_id=current_parent_id,
                                            source_id="",
                                            source_file=self.source_file,
                                            annex_number=annex_num,
                                            annex_part=current_part,
                                        )
                                    )
                        for p_tag in cell_copy.find_all("p"):
                            p_tag.decompose()
                        for fig in cell_copy.find_all("figure"):
                            fig.decompose()
                        for tbl in cell_copy.find_all("table"):
                            tbl.decompose()
                        bare_t = cell_copy.get_text(separator=" ", strip=True)
                        if bare_t and len(bare_t.strip()) >= 5:
                            annex_item_idx += 1
                            self._add_unit(
                                Unit(
                                    id=f"{current_parent_id}.item-{annex_item_idx}",
                                    type="annex_item",
                                    ref=None,
                                    text=normalize_text(bare_t),
                                    parent_id=current_parent_id,
                                    source_id="",
                                    source_file=self.source_file,
                                    annex_number=annex_num,
                                    annex_part=current_part,
                                )
                            )

            elif child.name == "p":
                classes = child.get("class", [])
                if any(c in classes for c in ("oj-doc-ti", "oj-ti-grseq-1")):
                    continue
                p_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=" ", strip=True)
                if text and len(text.strip()) >= 5:
                    annex_item_idx += 1
                    self._add_unit(
                        Unit(
                            id=f"{current_parent_id}.item-{annex_item_idx}",
                            type="annex_item",
                            ref=None,
                            text=normalize_text(text),
                            parent_id=current_parent_id,
                            source_id="",
                            source_file=self.source_file,
                            annex_number=annex_num,
                            annex_part=current_part,
                        )
                    )

            elif child.name == "div" and "oj-enumeration-spacing" in child.get("class", []):
                div_copy = BeautifulSoup(str(child), "lxml").find("div") or child
                remove_note_tags(div_copy)
                text = div_copy.get_text(separator=" ", strip=True)
                if text and len(text.strip()) >= 5:
                    annex_item_idx += 1
                    self._add_unit(
                        Unit(
                            id=f"{current_parent_id}.item-{annex_item_idx}",
                            type="annex_item",
                            ref=None,
                            text=normalize_text(text),
                            parent_id=current_parent_id,
                            source_id="",
                            source_file=self.source_file,
                            annex_number=annex_num,
                            annex_part=current_part,
                        )
                    )
