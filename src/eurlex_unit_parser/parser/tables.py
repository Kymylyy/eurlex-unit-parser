"""Table/list parsing logic shared by parser flows."""

from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup, Tag

from eurlex_unit_parser.labels import normalize_label
from eurlex_unit_parser.models import Unit
from eurlex_unit_parser.text_utils import (
    get_cell_text,
    is_list_table,
    normalize_text,
    remove_note_tags,
)


class TablesParserMixin:
    """Mixin that parses list-tables and extracts nested point structures."""

    def _extract_non_list_table_content(
        self,
        table: Tag,
        parent_id: str,
        article_num: Optional[str],
        paragraph_num: Optional[str],
        is_amendment: bool = False,
    ) -> None:
        parent_unit = next((u for u in self.units if u.id == parent_id), None)
        parent_type = parent_unit.type if parent_unit else "paragraph"
        child_type_map = {
            "paragraph": "subparagraph",
            "subparagraph": "point",
            "article": "point",
            "point": "subpoint",
            "annex_item": "subpoint",
            "subpoint": "subsubpoint",
            "subsubpoint": "nested_3",
        }
        child_type = child_type_map.get(parent_type, "subparagraph")

        if parent_type.startswith("nested_"):
            try:
                depth = int(parent_type.split("_")[1]) + 1
                child_type = f"nested_{depth}"
            except (ValueError, IndexError):
                pass

        sub_idx = 0
        for row in table.find_all("tr"):
            for cell in row.find_all(["td", "th"]):
                cell_copy = BeautifulSoup(str(cell), "lxml").find(["td", "th"]) or cell
                remove_note_tags(cell_copy)
                paragraphs = cell_copy.find_all("p")
                texts = []
                if paragraphs:
                    for p in paragraphs:
                        t = p.get_text(separator=" ", strip=True)
                        if t and len(t.strip()) >= 10:
                            texts.append(normalize_text(t))
                for p in cell_copy.find_all("p"):
                    p.decompose()
                for fig in cell_copy.find_all("figure"):
                    fig.decompose()
                for tbl in cell_copy.find_all("table"):
                    tbl.decompose()
                bare_text = cell_copy.get_text(separator=" ", strip=True)
                if bare_text and len(bare_text.strip()) >= 10:
                    texts.append(normalize_text(bare_text))
                for t in texts:
                    sub_idx += 1
                    self._add_unit(
                        Unit(
                            id=f"{parent_id}.tbl-{sub_idx}",
                            type=child_type,
                            ref=None,
                            text=t,
                            parent_id=parent_id,
                            source_id="",
                            source_file=self.source_file,
                            article_number=article_num,
                            paragraph_number=paragraph_num,
                            subparagraph_index=sub_idx if child_type == "subparagraph" else None,
                            is_amendment_text=is_amendment,
                        )
                    )

    def _parse_point_tables(
        self,
        tables: list[Tag],
        parent_id: str,
        article_num: Optional[str],
        paragraph_num: Optional[str],
        depth: int = 0,
        max_depth: int = 10,
        is_amendment: bool = False,
    ) -> None:
        """
        Parse list-tables as points/subpoints.

        depth: 0 = point, 1 = subpoint, 2 = subsubpoint, 3+ = nested_N.
        """
        if depth >= max_depth:
            return

        for table in tables:
            if not is_list_table(table):
                self._extract_non_list_table_content(
                    table,
                    parent_id,
                    article_num,
                    paragraph_num,
                    is_amendment=is_amendment,
                )
                continue

            tbody = table.find("tbody", recursive=False)
            if tbody:
                rows = tbody.find_all("tr", recursive=False)
            else:
                rows = table.find_all("tr", recursive=False)

            for row in rows:
                cells = row.find_all("td", recursive=False)
                if len(cells) < 2:
                    continue

                label_cell = cells[0]
                content_cell = cells[1]

                label_p = label_cell.find("p", recursive=False)
                if label_p:
                    label_text = label_p.get_text(strip=True)
                else:
                    label_text = label_cell.get_text(strip=True)

                label_normalized, _label_type, is_quoted = normalize_label(label_text)

                content_text = get_cell_text(content_cell, exclude_nested_tables=True)
                content_text = normalize_text(content_text)

                type_names = ["point", "subpoint", "subsubpoint"]
                id_prefixes = ["pt", "sub", "subsub"]

                if depth < len(type_names):
                    unit_type = type_names[depth]
                    prefix = id_prefixes[depth]
                else:
                    unit_type = f"nested_{depth}"
                    prefix = f"n{depth}"

                unit_id = f"{parent_id}.{prefix}-{label_normalized}"

                point_label = label_normalized if depth == 0 else None
                subpoint_label = label_normalized if depth == 1 else None
                subsubpoint_label = label_normalized if depth == 2 else None
                extra_labels = [label_normalized] if depth > 2 else []

                unit = Unit(
                    id=unit_id,
                    type=unit_type,
                    ref=label_text,
                    text=content_text,
                    parent_id=parent_id,
                    source_id="",
                    source_file=self.source_file,
                    article_number=article_num,
                    paragraph_number=paragraph_num,
                    point_label=point_label,
                    subpoint_label=subpoint_label,
                    subsubpoint_label=subsubpoint_label,
                    extra_labels=extra_labels,
                    is_amendment_text=is_amendment or is_quoted,
                )
                self._add_unit(unit)

                nested_tables = content_cell.find_all("table", recursive=False)
                if nested_tables:
                    self._parse_point_tables(
                        nested_tables,
                        unit_id,
                        article_num,
                        paragraph_num,
                        depth=depth + 1,
                        max_depth=max_depth,
                        is_amendment=is_amendment,
                    )

                    cont_idx = 0
                    first_p_seen = False
                    for child in content_cell.children:
                        if not isinstance(child, Tag):
                            continue
                        if child.name == "p":
                            if "oj-note" in child.get("class", []):
                                continue
                            if not first_p_seen:
                                first_p_seen = True
                                continue
                            p_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                            remove_note_tags(p_copy)
                            t = p_copy.get_text(separator=" ", strip=True)
                            if t and len(t.strip()) >= 3:
                                cont_idx += 1
                                cont_id = f"{unit_id}.cont-{cont_idx}"
                                next_depth = depth + 1
                                if next_depth < len(type_names):
                                    cont_type = type_names[next_depth]
                                else:
                                    cont_type = f"nested_{next_depth}"
                                self._add_unit(
                                    Unit(
                                        id=cont_id,
                                        type=cont_type,
                                        ref=None,
                                        text=normalize_text(t),
                                        parent_id=unit_id,
                                        source_id="",
                                        source_file=self.source_file,
                                        article_number=article_num,
                                        paragraph_number=paragraph_num,
                                        is_amendment_text=is_amendment,
                                    )
                                )

                cell_copy = BeautifulSoup(str(content_cell), "lxml").find("td") or content_cell
                remove_note_tags(cell_copy)
                for tag in cell_copy.find_all(["p", "figure", "table", "div"]):
                    tag.decompose()
                bare_text = cell_copy.get_text(separator=" ", strip=True)
                if bare_text and len(bare_text.strip()) >= 10:
                    next_depth = depth + 1
                    if next_depth < len(type_names):
                        bare_type = type_names[next_depth]
                    else:
                        bare_type = f"nested_{next_depth}"
                    self._add_unit(
                        Unit(
                            id=f"{unit_id}.bare-1",
                            type=bare_type,
                            ref=None,
                            text=normalize_text(bare_text),
                            parent_id=unit_id,
                            source_id="",
                            source_file=self.source_file,
                            article_number=article_num,
                            paragraph_number=paragraph_num,
                            is_amendment_text=is_amendment,
                        )
                    )

                div_cont_idx = 0
                for div_child in content_cell.find_all("div", recursive=False):
                    for p in div_child.find_all("p", recursive=False):
                        classes = set(p.get("class", []))
                        if classes & {"oj-ti-art", "oj-sti-art", "oj-doc-ti"}:
                            continue
                        p_copy = BeautifulSoup(str(p), "lxml").find("p") or p
                        remove_note_tags(p_copy)
                        t = p_copy.get_text(separator=" ", strip=True)
                        if t and len(t.strip()) >= 10:
                            div_cont_idx += 1
                            next_depth = depth + 1
                            if next_depth < len(type_names):
                                div_type = type_names[next_depth]
                            else:
                                div_type = f"nested_{next_depth}"
                            self._add_unit(
                                Unit(
                                    id=f"{unit_id}.div-{div_cont_idx}",
                                    type=div_type,
                                    ref=None,
                                    text=normalize_text(t),
                                    parent_id=unit_id,
                                    source_id="",
                                    source_file=self.source_file,
                                    article_number=article_num,
                                    paragraph_number=paragraph_num,
                                    is_amendment_text=is_amendment,
                                )
                            )
