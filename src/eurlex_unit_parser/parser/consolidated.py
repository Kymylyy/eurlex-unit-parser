"""Consolidated-format parsing flow."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

from eurlex_unit_parser.labels import normalize_label
from eurlex_unit_parser.models import Unit
from eurlex_unit_parser.text_utils import normalize_text, remove_note_tags


class ConsolidatedParserMixin:
    """Mixin implementing parser logic for consolidated CELEX pages."""

    def _parse_articles_consolidated(self) -> None:
        article_divs = self.soup.find_all(
            "div", class_="eli-subdivision", id=lambda x: x and x.startswith("art_")
        )

        for div in article_divs:
            source_id = div.get("id", "")
            article_num = source_id.replace("art_", "")

            title_p = div.find("p", class_="title-article-norm")
            _article_title = title_p.get_text(strip=True) if title_p else f"Article {article_num}"

            subtitle = None
            subtitle_p = div.find("p", class_="stitle-article-norm")
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

            self._parse_consolidated_content(div, article_id, article_num)

    def _parse_consolidated_content(self, parent_div: Tag, parent_id: str, article_num: str) -> None:
        intro_idx = 0
        for child in parent_div.children:
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
                    par_num_text = no_parag.get_text(strip=True).rstrip(".")
                    par_num = re.sub(r"[^\d]", "", par_num_text)

                    par_id = f"{parent_id}.par-{par_num}" if par_num else parent_id

                    inline_div = child.find("div", class_="inline-element", recursive=False)
                    if inline_div:
                        par_text = self._get_consolidated_text(inline_div)
                    else:
                        child_copy = BeautifulSoup(str(child), "lxml").find("div") or child
                        remove_note_tags(child_copy)
                        par_text = child_copy.get_text(separator=" ", strip=True)
                        par_text = par_text.replace(no_parag.get_text(), "", 1).strip()

                    par_unit = Unit(
                        id=par_id,
                        type="paragraph",
                        ref=f"{par_num}." if par_num else None,
                        text=normalize_text(par_text),
                        parent_id=parent_id,
                        source_id="",
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=par_num,
                    )
                    self._add_unit(par_unit)

                    self._parse_consolidated_points(child, par_id, article_num, par_num)

            elif child.name == "div" and "grid-container" in child.get("class", []):
                self._parse_single_grid_point(child, parent_id, article_num, None, depth=0)

            elif child.name == "p" and "norm" in child.get("class", []):
                child_copy = BeautifulSoup(str(child), "lxml").find("p") or child
                remove_note_tags(child_copy)
                intro_text = child_copy.get_text(separator=" ", strip=True)
                if intro_text:
                    intro_idx += 1
                    intro_unit = Unit(
                        id=f"{parent_id}.intro-{intro_idx}",
                        type="intro",
                        ref=None,
                        text=normalize_text(intro_text),
                        parent_id=parent_id,
                        source_id=child.get("id", ""),
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=None,
                        paragraph_index=None,
                    )
                    self._add_unit(intro_unit)

    def _parse_consolidated_points(
        self,
        parent: Tag,
        parent_id: str,
        article_num: str,
        paragraph_num: Optional[str],
        depth: int = 0,
    ) -> None:
        grid_lists = parent.find_all("div", class_="grid-container", recursive=False)

        inline_div = parent.find("div", class_="inline-element", recursive=False)
        if inline_div:
            grid_lists.extend(inline_div.find_all("div", class_="grid-container", recursive=False))

        for grid in grid_lists:
            self._parse_single_grid_point(grid, parent_id, article_num, paragraph_num, depth)

    def _parse_single_grid_point(
        self,
        grid: Tag,
        parent_id: str,
        article_num: str,
        paragraph_num: Optional[str],
        depth: int,
    ) -> None:
        if depth > 10:
            return

        label_div = grid.find("div", class_="grid-list-column-1")
        if not label_div:
            label_div = grid.find("div", class_="list")
        label_text = ""
        if label_div:
            span = label_div.find("span")
            if span:
                label_text = span.get_text(strip=True)
            else:
                label_text = label_div.get_text(strip=True)

        content_div = grid.find("div", class_="grid-list-column-2")
        content_text = ""
        if content_div:
            content_text = self._get_consolidated_text(content_div)

        label_normalized, _label_type, is_quoted = normalize_label(label_text)

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

        unit = Unit(
            id=unit_id,
            type=unit_type,
            ref=label_text,
            text=normalize_text(content_text),
            parent_id=parent_id,
            source_id="",
            source_file=self.source_file,
            article_number=article_num,
            paragraph_number=paragraph_num,
            point_label=point_label,
            subpoint_label=subpoint_label,
            subsubpoint_label=subsubpoint_label,
            is_amendment_text=is_quoted,
        )
        self._add_unit(unit)

        if content_div:
            nested_grids = content_div.find_all("div", class_="grid-container", recursive=False)
            for nested in nested_grids:
                self._parse_single_grid_point(nested, unit_id, article_num, paragraph_num, depth + 1)

    def _get_consolidated_text(self, element: Tag) -> str:
        clone = BeautifulSoup(str(element), "lxml")
        root = clone.find("div") or clone.find("p") or clone
        remove_note_tags(root)

        for grid in root.find_all("div", class_="grid-container"):
            grid.decompose()

        texts = []
        for p in root.find_all("p", class_="norm"):
            remove_note_tags(p)
            text = p.get_text(separator=" ", strip=True)
            if text:
                texts.append(text)

        if texts:
            return " ".join(texts)

        return root.get_text(separator=" ", strip=True)
