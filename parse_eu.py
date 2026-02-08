#!/usr/bin/env python3
"""
Universal EU OJ (ELI) Parser

Parses ELI-style Official Journal HTML files and outputs a flat JSON array
of units (recitals, articles, paragraphs, points, subpoints, annexes).
"""

import argparse
import json
import re
import sys
import warnings
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

# Suppress XML parsed as HTML warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Unit:
    """Represents a single parsed unit (recital, article, paragraph, point, etc.)."""
    id: str
    type: str  # recital, article, paragraph, point, subpoint, subsubpoint, annex, annex_item
    ref: Optional[str]  # raw label text e.g. "(a)", "1.", "(i)"
    text: str
    parent_id: Optional[str]
    source_id: str  # original HTML id attribute
    source_file: str

    # Hierarchical metadata
    article_number: Optional[str] = None
    paragraph_number: Optional[str] = None
    paragraph_index: Optional[int] = None  # if no explicit number
    point_label: Optional[str] = None
    subpoint_label: Optional[str] = None
    subsubpoint_label: Optional[str] = None
    extra_labels: list = field(default_factory=list)

    # Additional metadata
    heading: Optional[str] = None  # article title or annex heading
    annex_number: Optional[str] = None
    annex_part: Optional[str] = None
    recital_number: Optional[str] = None

    # Amendment metadata
    is_amendment_text: bool = False  # True if this is quoted replacement text in amendments

    # Debug
    source_xpath: Optional[str] = None


@dataclass
class ValidationReport:
    """Validation report for a parsed file."""
    source_file: str
    counts_expected: dict = field(default_factory=dict)
    counts_parsed: dict = field(default_factory=dict)
    sequence_gaps: list = field(default_factory=list)
    orphans: list = field(default_factory=list)
    unparsed_nodes: list = field(default_factory=list)
    mismatched_labels: list = field(default_factory=list)

    def is_valid(self) -> bool:
        return (
            not self.sequence_gaps and
            not self.orphans and
            not self.unparsed_nodes and
            not self.mismatched_labels
        )


# =============================================================================
# Label Parsing Utilities
# =============================================================================

# Regex patterns for label extraction
PARAGRAPH_NUM_RE = re.compile(r'^(\d+)\.\s*')
# Point labels: (a), (b), (aa), (ab), etc. - single or double letter
POINT_LABEL_RE = re.compile(r'^\(?([a-z]{1,2})\)?$', re.IGNORECASE)
# Subpoint labels (roman numerals): (i), (ii), (iii), (iv), (v), (vi), (xxii), etc.
# Supports Roman numerals up to ~39 (xxxix)
# Must be careful not to confuse with single letters like 'i', 'v', 'x'
SUBPOINT_LABEL_RE = re.compile(
    r'^\(?('
    r'i{1,3}|iv|v|vi{0,3}|ix|'                    # 1-9
    r'x{1,3}|xi{0,3}|xiv|xv|xvi{0,3}|xix|'        # 10-19
    r'xxi{0,3}|xxiv|xxv|xxvi{0,3}|xxix|'          # 20-29
    r'xxxi{0,3}|xxxiv|xxxv|xxxvi{0,3}|xxxix'      # 30-39
    r')\)?$', re.IGNORECASE
)
# Numeric labels: (1), (2), 1., 2), 1, etc.
NUMERIC_LABEL_RE = re.compile(r'^\(?(\d+)\)?[.\)]?$')
# Dash labels
DASH_LABEL_RE = re.compile(r'^[—–-]$')
# Quote characters used in amendments
QUOTE_CHARS = "'\u2018\u2019"


def normalize_label(label: str) -> tuple[str, str, bool]:
    """
    Normalize a label and determine its type.

    Returns: (normalized_label, label_type, is_quoted)
    label_type: 'paragraph', 'point', 'subpoint', 'numeric', 'dash', 'unknown'
    is_quoted: True if label started with quote (amendment text)
    """
    label = label.strip()
    is_quoted = False

    # Check for and strip leading quote (amendment text marker)
    if label and label[0] in QUOTE_CHARS:
        is_quoted = True
        label = label[1:].strip()

    # Paragraph number: "1.", "2.", etc. (without parentheses)
    m = PARAGRAPH_NUM_RE.match(label)
    if m and '(' not in label:
        return m.group(1), 'paragraph', is_quoted

    # Numeric in parentheses: (1), (2), etc. or without: 1., 1), 1
    m = NUMERIC_LABEL_RE.match(label)
    if m:
        return m.group(1), 'numeric', is_quoted

    # Subpoint label (roman): (i), (ii), (iii), etc.
    # Check this BEFORE point to avoid misclassifying 'i', 'v', 'x' as points
    m = SUBPOINT_LABEL_RE.match(label)
    if m:
        return m.group(1).lower(), 'subpoint', is_quoted

    # Point label: (a), (b), a), a, etc.
    m = POINT_LABEL_RE.match(label)
    if m:
        return m.group(1).lower(), 'point', is_quoted

    # Dash
    if DASH_LABEL_RE.match(label):
        return '—', 'dash', is_quoted

    return label, 'unknown', is_quoted


def is_list_table(table: Tag) -> bool:
    """
    Heuristic to determine if a table is a list-table (2 columns, label in left).
    """
    # Find <col> elements - either direct children or inside <colgroup>
    cols = table.find_all('col', recursive=False)
    if not cols:
        # Try finding cols inside colgroup
        colgroup = table.find('colgroup', recursive=False)
        if colgroup:
            cols = colgroup.find_all('col', recursive=False)
    has_cols = len(cols) == 2

    if has_cols:
        # Check if left column is narrow (typically 4-5%)
        first_col = cols[0]
        width = first_col.get('width', '')
        if '%' in width:
            try:
                pct = int(width.replace('%', ''))
                if pct > 15:  # Allow slightly wider columns
                    return False
            except ValueError:
                pass

    # Find tbody, then tr
    tbody = table.find('tbody', recursive=False)
    if not tbody:
        # Try finding tr directly under table
        first_row = table.find('tr', recursive=False)
    else:
        first_row = tbody.find('tr', recursive=False)

    if first_row:
        tds = first_row.find_all('td', recursive=False)
        # Without <col> elements, require exactly 2 cells
        if not has_cols and len(tds) != 2:
            return False
        first_td = tds[0] if tds else None
        if first_td:
            # Get raw text, handling <p> elements (but only direct children)
            p_elem = first_td.find('p', recursive=False)
            if p_elem:
                text = p_elem.get_text(strip=True)
            else:
                text = first_td.get_text(strip=True)

            # Check if it looks like a label (short, matches pattern)
            if len(text) <= 15:  # Labels can be like "(iii)" or "(10)" or "'(a)"
                _, label_type, _ = normalize_label(text)
                if label_type != 'unknown':
                    return True

    return False


# =============================================================================
# Text Extraction Utilities
# =============================================================================

def remove_note_tags(element: Tag) -> None:
    """Remove footnote anchors and superscript note tags from element."""
    # Remove <a> tags with note references
    for a in element.find_all('a', href=True):
        href = a.get('href', '')
        if '#ntr' in href or '#ntc' in href:
            a.decompose()
            continue
        classes = a.get('class', []) or []
        if any('note' in c for c in classes):
            a.decompose()

    # Remove superscript note tags
    for span in element.find_all('span', class_='oj-note-tag'):
        span.decompose()
    for span in element.find_all('span', class_='oj-super'):
        # Only remove footnote-like markers (digits, *digits), keep content superscripts
        text = span.get_text(strip=True)
        if re.match(r'^[*]?\d+$', text):
            span.decompose()


def get_cell_text(cell: Tag, exclude_nested_tables: bool = False) -> str:
    """
    Extract text from a table cell, optionally excluding nested tables.
    When exclude_nested_tables=True, only returns text from <p> elements
    that appear before the first nested <table>.
    """
    cell_copy = BeautifulSoup(str(cell), 'lxml').find('td') or cell
    remove_note_tags(cell_copy)

    if exclude_nested_tables:
        # Check if there are nested tables or div wrappers — if so, only return FIRST <p> text
        # (subsequent <p> elements are captured by the cont logic in _parse_point_tables)
        has_nested = bool(cell_copy.find('table', recursive=False) or
                          cell_copy.find('div', recursive=False))
        texts = []
        for child in cell_copy.children:
            if isinstance(child, NavigableString):
                t = child.strip()
                if t:
                    texts.append(t)
                continue
            if not isinstance(child, Tag):
                continue
            if child.name == 'table':
                break  # Stop at first nested table
            if child.name == 'p':
                if 'oj-note' in child.get('class', []):
                    continue  # Skip footnote paragraphs
                text = child.get_text(separator=' ', strip=True)
                if text:
                    texts.append(text)
                    if has_nested:
                        break  # Only first <p> when nested tables follow
        if texts:
            return ' '.join(texts)
        # Fallback: get all text with tables removed
        for nested_table in cell_copy.find_all('table'):
            nested_table.decompose()
        return cell_copy.get_text(separator=' ', strip=True)

    # Get text from all <p> elements, joining with space
    paragraphs = cell_copy.find_all('p', recursive=False)
    if paragraphs:
        texts = [p.get_text(separator=' ', strip=True) for p in paragraphs if p.get_text(strip=True)]
        return ' '.join(texts)

    # Fallback: get all text
    return cell_copy.get_text(separator=' ', strip=True)


def normalize_text(text: str) -> str:
    """Normalize whitespace in text."""
    # Collapse multiple spaces/newlines to single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def strip_leading_label(text: str) -> tuple[str, Optional[str]]:
    """
    Strip leading label from text (e.g., "1. Some text" -> ("Some text", "1"))
    Returns: (text_without_label, extracted_label)
    """
    # Match paragraph-style: "1.   Text"
    m = re.match(r'^(\d+)\.\s+(.*)$', text, re.DOTALL)
    if m:
        return m.group(2).strip(), m.group(1)

    return text, None


# =============================================================================
# Core Parser
# =============================================================================

class EUParser:
    """Parser for EU Official Journal HTML files."""

    def __init__(self, source_file: str):
        self.source_file = source_file
        self.units: list[Unit] = []
        self.validation = ValidationReport(source_file=source_file)
        self._unit_ids: set[str] = set()
        self.is_consolidated = False

    def parse(self, html_content: str) -> list[Unit]:
        """Parse HTML content and return list of units."""
        self.soup = BeautifulSoup(html_content, 'lxml')

        # Detect format (OJ vs Consolidated)
        self._detect_format()

        # Count expected elements for validation
        self._count_expected_elements()

        # Parse recitals (OJ format only - consolidated doesn't have them)
        self._parse_recitals()

        # Parse articles (different methods for OJ vs consolidated)
        if self.is_consolidated:
            self._parse_articles_consolidated()
        else:
            self._parse_articles()

        # Parse annexes
        self._parse_annexes()

        # Update parsed counts
        self._count_parsed_elements()

        # Validate
        self._validate()

        return self.units

    def _detect_format(self):
        """Detect if this is OJ format or consolidated (CELEX) format."""
        # Consolidated format markers:
        # - Uses <p class="title-article-norm"> for article titles
        # - Uses <div class="norm"> for paragraphs
        # - Uses <div class="grid-container grid-list"> for points
        if self.soup.find('p', class_='title-article-norm'):
            self.is_consolidated = True
        elif self.soup.find('div', class_='grid-container'):
            self.is_consolidated = True
        else:
            self.is_consolidated = False

    def _count_expected_elements(self):
        """Count expected elements from HTML structure."""
        self.validation.counts_expected = {
            'recitals': len(self.soup.find_all('div', class_='eli-subdivision', id=lambda x: x and x.startswith('rct_'))),
            'articles': len(self.soup.find_all('div', class_='eli-subdivision', id=lambda x: x and x.startswith('art_'))),
            'annexes': len(self.soup.find_all('div', class_='eli-container', id=lambda x: x and x.startswith('anx_'))),
        }

    def _count_parsed_elements(self):
        """Count parsed elements by type."""
        counts = {}
        for unit in self.units:
            counts[unit.type] = counts.get(unit.type, 0) + 1
        self.validation.counts_parsed = counts

    def _add_unit(self, unit: Unit):
        """Add a unit, ensuring unique ID."""
        if unit.id in self._unit_ids:
            # Generate unique ID by appending suffix
            suffix = 1
            base_id = unit.id
            while unit.id in self._unit_ids:
                unit.id = f"{base_id}_{suffix}"
                suffix += 1
        self._unit_ids.add(unit.id)
        self.units.append(unit)

    # -------------------------------------------------------------------------
    # Recital Parsing
    # -------------------------------------------------------------------------

    def _parse_recitals(self):
        """Parse all recitals."""
        recital_divs = self.soup.find_all('div', class_='eli-subdivision',
                                          id=lambda x: x and x.startswith('rct_'))

        for div in recital_divs:
            source_id = div.get('id', '')
            recital_num = source_id.replace('rct_', '')

            # Find text - either in table or direct <p>
            table = div.find('table')
            if table and is_list_table(table):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        label_text = get_cell_text(cells[0]).strip()
                        content_text = get_cell_text(cells[1])

                        # Extract number from label like "(1)"
                        m = re.match(r'\((\d+)\)', label_text)
                        if m:
                            recital_num = m.group(1)

                        unit = Unit(
                            id=f"recital-{recital_num}",
                            type='recital',
                            ref=label_text,
                            text=normalize_text(content_text),
                            parent_id=None,
                            source_id=source_id,
                            source_file=self.source_file,
                            recital_number=recital_num,
                        )
                        self._add_unit(unit)
            else:
                # Direct <p> content - combine ALL <p> elements in recital
                p_elements = div.find_all('p', class_='oj-normal')
                if p_elements:
                    # Combine text from all paragraphs (some recitals span multiple <p>)
                    combined_parts = []
                    for p in p_elements:
                        p_copy = BeautifulSoup(str(p), 'lxml').find('p')
                        remove_note_tags(p_copy)
                        p_text = p_copy.get_text(separator=' ', strip=True)
                        p_text, _ = strip_leading_label(p_text)
                        if p_text:
                            combined_parts.append(p_text)
                    text = ' '.join(combined_parts)
                    unit = Unit(
                        id=f"recital-{recital_num}",
                        type='recital',
                        ref=f"({recital_num})",
                        text=normalize_text(text),
                        parent_id=None,
                        source_id=source_id,
                        source_file=self.source_file,
                        recital_number=recital_num,
                    )
                    self._add_unit(unit)

    # -------------------------------------------------------------------------
    # Article Parsing
    # -------------------------------------------------------------------------

    def _parse_articles(self):
        """Parse all articles."""
        article_divs = self.soup.find_all('div', class_='eli-subdivision',
                                          id=lambda x: x and x.startswith('art_'))

        for div in article_divs:
            source_id = div.get('id', '')
            article_num = source_id.replace('art_', '')

            # Get article title
            title_p = div.find('p', class_='oj-ti-art')
            article_title = title_p.get_text(strip=True) if title_p else f"Article {article_num}"

            # Get article subtitle (if any)
            subtitle = None
            subtitle_div = div.find('div', class_='eli-title')
            if subtitle_div:
                subtitle_p = subtitle_div.find('p', class_='oj-sti-art')
                if subtitle_p:
                    subtitle = subtitle_p.get_text(strip=True)

            # Create article unit
            article_id = f"art-{article_num}"
            article_unit = Unit(
                id=article_id,
                type='article',
                ref=f"Article {article_num}",
                text="",  # Articles typically don't have direct text
                parent_id=None,
                source_id=source_id,
                source_file=self.source_file,
                article_number=article_num,
                heading=subtitle,
            )
            self._add_unit(article_unit)

            # Detect amending article
            is_amending = False
            if subtitle and re.search(r'Amendments?\s+to\b|Amendment\s+of\b', subtitle, re.IGNORECASE):
                is_amending = True
            if not is_amending:
                first_p = div.find('p', class_='oj-normal')
                if first_p:
                    ft = first_p.get_text(strip=True)[:200]
                    if 'is amended as follows' in ft or 'are amended as follows' in ft:
                        is_amending = True

            if is_amending:
                self._parse_amending_article(div, article_id, article_num)
                continue

            # Parse paragraphs (divs with id like "001.001", "001.002")
            paragraph_divs = div.find_all('div', id=re.compile(r'^\d{3}\.\d{3}$'), recursive=False)

            if paragraph_divs:
                self._parse_paragraphs(paragraph_divs, article_id, article_num)
            else:
                # Article without explicit paragraphs - parse direct content
                self._parse_article_direct_content(div, article_id, article_num)

    def _parse_paragraphs(self, paragraph_divs: list[Tag], article_id: str, article_num: str):
        """Parse paragraph divs within an article."""
        for idx, par_div in enumerate(paragraph_divs):
            par_source_id = par_div.get('id', '')
            par_num = None
            par_id = None
            current_parent = None  # Tracks current parent for points
            subpar_idx = 0
            pending_tables = []

            # Iterate over direct children in DOM order
            for child in par_div.children:
                if not isinstance(child, Tag):
                    # Capture significant bare text nodes (e.g. post-formula text)
                    if isinstance(child, NavigableString) and par_id is not None:
                        bare = child.strip()
                        if bare and len(bare) >= 10:
                            subpar_idx += 1
                            subpar_id = f"{par_id}.subpar-{subpar_idx}"
                            self._add_unit(Unit(
                                id=subpar_id, type='subparagraph', ref=None,
                                text=normalize_text(bare), parent_id=par_id,
                                source_id='', source_file=self.source_file,
                                article_number=article_num, paragraph_number=par_num,
                            ))
                            current_parent = subpar_id
                    continue

                # <p class="oj-normal"> or <p class="oj-ti-tbl"> - paragraph or subparagraph
                if child.name == 'p' and ('oj-normal' in child.get('class', []) or 'oj-ti-tbl' in child.get('class', []) or 'oj-note' in child.get('class', [])):
                    # Parse any pending tables BEFORE processing new <p>
                    # Tables belong to the previous parent (the one that introduced them)
                    if pending_tables and current_parent:
                        self._parse_point_tables(pending_tables, current_parent, article_num, par_num)
                        pending_tables = []

                    p_copy = BeautifulSoup(str(child), 'lxml').find('p') or child
                    remove_note_tags(p_copy)
                    text = p_copy.get_text(separator=' ', strip=True)

                    if par_id is None:
                        # First <p> is the main paragraph (with number)
                        text_content, par_num = strip_leading_label(text)
                        par_id = f"{article_id}.par-{par_num}" if par_num else f"{article_id}.par-{idx+1}"

                        par_unit = Unit(
                            id=par_id,
                            type='paragraph',
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
                        # Subsequent <p> is a subparagraph
                        subpar_idx += 1
                        subpar_id = f"{par_id}.subpar-{subpar_idx}"

                        subpar_unit = Unit(
                            id=subpar_id,
                            type='subparagraph',
                            ref=None,
                            text=normalize_text(text),
                            parent_id=par_id,
                            source_id=child.get('id', ''),
                            source_file=self.source_file,
                            article_number=article_num,
                            paragraph_number=par_num,
                        )
                        self._add_unit(subpar_unit)
                        current_parent = subpar_id  # Points go under this subparagraph

                # <table> - collect for point parsing
                elif child.name == 'table':
                    pending_tables.append(child)

                # Unnamed <div> wrapper — extract <p class="oj-normal"> from within
                elif child.name == 'div':
                    child_id = child.get('id', '')
                    child_classes = child.get('class', [])
                    if not child_id and 'eli-subdivision' not in child_classes and 'eli-title' not in child_classes:
                        for p in child.find_all('p', class_='oj-normal', recursive=False):
                            if pending_tables and current_parent:
                                self._parse_point_tables(pending_tables, current_parent, article_num, par_num)
                                pending_tables = []

                            p_copy = BeautifulSoup(str(p), 'lxml').find('p') or p
                            remove_note_tags(p_copy)
                            text = p_copy.get_text(separator=' ', strip=True)

                            if par_id is None:
                                text_content, par_num = strip_leading_label(text)
                                par_id = f"{article_id}.par-{par_num}" if par_num else f"{article_id}.par-{idx+1}"
                                self._add_unit(Unit(
                                    id=par_id, type='paragraph', ref=f"{par_num}." if par_num else None,
                                    text=normalize_text(text_content), parent_id=article_id,
                                    source_id=par_source_id, source_file=self.source_file,
                                    article_number=article_num, paragraph_number=par_num,
                                    paragraph_index=idx + 1 if not par_num else None,
                                ))
                                current_parent = par_id
                            else:
                                subpar_idx += 1
                                subpar_id = f"{par_id}.subpar-{subpar_idx}"
                                self._add_unit(Unit(
                                    id=subpar_id, type='subparagraph', ref=None,
                                    text=normalize_text(text), parent_id=par_id,
                                    source_id=p.get('id', ''), source_file=self.source_file,
                                    article_number=article_num, paragraph_number=par_num,
                                ))
                                current_parent = subpar_id

            # Parse any remaining tables at end of paragraph div
            if pending_tables:
                if current_parent is None:
                    # No <p> found — paragraph is table-only, create container from div ID
                    m = re.search(r'\.(\d+)', par_source_id)
                    par_num = str(int(m.group(1))) if m else str(idx + 1)
                    par_id = f"{article_id}.par-{par_num}"
                    self._add_unit(Unit(
                        id=par_id, type='paragraph', ref=f"{par_num}.",
                        text='', parent_id=article_id,
                        source_id=par_source_id, source_file=self.source_file,
                        article_number=article_num, paragraph_number=par_num,
                    ))
                    current_parent = par_id
                self._parse_point_tables(pending_tables, current_parent, article_num, par_num)

    def _parse_article_direct_content(self, article_div: Tag, article_id: str, article_num: str):
        """Parse article content when there are no explicit paragraph divs."""
        # Skip title elements
        title_div = article_div.find('div', class_='eli-title')

        par_id = None
        current_parent = None
        subpar_idx = 0
        pending_tables = []

        # Iterate over direct children in DOM order
        for child in article_div.children:
            if not isinstance(child, Tag):
                continue

            # Skip title div and its contents
            if child == title_div:
                continue
            if child.name == 'p' and 'oj-ti-art' in child.get('class', []):
                continue
            if child.name == 'p' and 'oj-sti-art' in child.get('class', []):
                continue

            # <p class="oj-normal"> or <p class="oj-ti-tbl"> - paragraph or subparagraph
            if child.name == 'p' and ('oj-normal' in child.get('class', []) or 'oj-ti-tbl' in child.get('class', []) or 'oj-note' in child.get('class', [])):
                # Parse any pending tables BEFORE processing new <p>
                # Tables belong to the previous parent (the one that introduced them)
                if pending_tables and current_parent:
                    self._parse_point_tables(pending_tables, current_parent, article_num, None, is_direct=True)
                    pending_tables = []

                p_copy = BeautifulSoup(str(child), 'lxml').find('p') or child
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=' ', strip=True)

                if par_id is None:
                    # First <p> is the main paragraph
                    par_id = f"{article_id}.par-1"
                    par_unit = Unit(
                        id=par_id,
                        type='paragraph',
                        ref=None,
                        text=normalize_text(text),
                        parent_id=article_id,
                        source_id=child.get('id', ''),
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=None,
                        paragraph_index=1,
                    )
                    self._add_unit(par_unit)
                    current_parent = par_id
                else:
                    # Subsequent <p> is a subparagraph
                    subpar_idx += 1
                    subpar_id = f"{par_id}.subpar-{subpar_idx}"

                    subpar_unit = Unit(
                        id=subpar_id,
                        type='subparagraph',
                        ref=None,
                        text=normalize_text(text),
                        parent_id=par_id,
                        source_id=child.get('id', ''),
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=None,
                    )
                    self._add_unit(subpar_unit)
                    current_parent = subpar_id

            # <table> - collect for point parsing
            elif child.name == 'table':
                pending_tables.append(child)

            # Unnamed <div> wrapper — extract <p class="oj-normal"> from within
            elif child.name == 'div' and child != title_div:
                child_id = child.get('id', '')
                child_classes = child.get('class', [])
                if not child_id and 'eli-subdivision' not in child_classes and 'eli-title' not in child_classes:
                    for p in child.find_all('p', class_='oj-normal', recursive=False):
                        if pending_tables and current_parent:
                            self._parse_point_tables(pending_tables, current_parent, article_num, None, is_direct=True)
                            pending_tables = []

                        p_copy = BeautifulSoup(str(p), 'lxml').find('p') or p
                        remove_note_tags(p_copy)
                        text = p_copy.get_text(separator=' ', strip=True)

                        if par_id is None:
                            par_id = f"{article_id}.par-1"
                            self._add_unit(Unit(
                                id=par_id, type='paragraph', ref=None,
                                text=normalize_text(text), parent_id=article_id,
                                source_id=p.get('id', ''), source_file=self.source_file,
                                article_number=article_num, paragraph_number=None, paragraph_index=1,
                            ))
                            current_parent = par_id
                        else:
                            subpar_idx += 1
                            subpar_id = f"{par_id}.subpar-{subpar_idx}"
                            self._add_unit(Unit(
                                id=subpar_id, type='subparagraph', ref=None,
                                text=normalize_text(text), parent_id=par_id,
                                source_id=p.get('id', ''), source_file=self.source_file,
                                article_number=article_num, paragraph_number=None,
                            ))
                            current_parent = subpar_id

        # Parse any remaining tables at end of article div
        if pending_tables and current_parent:
            self._parse_point_tables(pending_tables, current_parent, article_num, None, is_direct=True)

    def _parse_amending_article(self, article_div: Tag, article_id: str, article_num: str):
        """Parse amending article — DOM-order walk routing list-tables to point parser."""
        skip_classes = {'oj-ti-art', 'oj-sti-art', 'oj-doc-ti'}
        par_id = f"{article_id}.par-1"
        par_created = False
        subpar_idx = 0
        seen_texts: set[str] = set()
        first_p = True  # First non-heading <p> becomes paragraph

        def ensure_paragraph():
            """Create paragraph container if not yet created (e.g. table before first <p>)."""
            nonlocal par_created
            if not par_created:
                self._add_unit(Unit(
                    id=par_id, type='paragraph', ref=None,
                    text='', parent_id=article_id, source_id="",
                    source_file=self.source_file,
                    article_number=article_num,
                    is_amendment_text=True,
                ))
                par_created = True

        def walk(container: Tag):
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
                            self._add_unit(Unit(
                                id=f"{par_id}.subpar-{subpar_idx}",
                                type='subparagraph', ref=None,
                                text=text, parent_id=par_id, source_id="",
                                source_file=self.source_file,
                                article_number=article_num,
                                is_amendment_text=True,
                            ))
                    continue

                if not isinstance(child, Tag):
                    continue

                if child.name == 'p':
                    classes = set(child.get('class', []))
                    if classes & skip_classes:
                        continue
                    p_copy = BeautifulSoup(str(child), 'lxml').find('p') or child
                    remove_note_tags(p_copy)
                    text = p_copy.get_text(separator=' ', strip=True)
                    if not text or len(text.strip()) < 3:
                        continue
                    text, label = strip_leading_label(text)
                    text = normalize_text(text)
                    if text in seen_texts:
                        continue
                    seen_texts.add(text)

                    if first_p and not par_created:
                        # First <p> becomes the paragraph unit
                        self._add_unit(Unit(
                            id=par_id, type='paragraph',
                            ref=f"{label}." if label else None,
                            text=text, parent_id=article_id, source_id="",
                            source_file=self.source_file,
                            article_number=article_num,
                            is_amendment_text=True,
                        ))
                        par_created = True
                        first_p = False
                    else:
                        ensure_paragraph()
                        subpar_idx += 1
                        self._add_unit(Unit(
                            id=f"{par_id}.subpar-{subpar_idx}",
                            type='subparagraph', ref=None,
                            text=text, parent_id=par_id, source_id="",
                            source_file=self.source_file,
                            article_number=article_num,
                            is_amendment_text=True,
                        ))
                        first_p = False

                elif child.name == 'table':
                    ensure_paragraph()
                    if is_list_table(child):
                        self._parse_point_tables(
                            [child], par_id, article_num,
                            paragraph_num=None, depth=0,
                            is_amendment=True,
                        )
                    else:
                        self._extract_non_list_table_content(
                            child, par_id, article_num,
                            paragraph_num=None, is_amendment=True,
                        )

                elif child.name == 'div':
                    walk(child)

                elif child.name == 'figure':
                    continue  # Formulas — skip

                else:
                    # Unknown tag — emit as unknown_unit if substantive text
                    text = child.get_text(separator=' ', strip=True)
                    if text and len(text) >= 10:
                        text = normalize_text(text)
                        if text not in seen_texts:
                            seen_texts.add(text)
                            ensure_paragraph()
                            subpar_idx += 1
                            self._add_unit(Unit(
                                id=f"{par_id}.unk-{subpar_idx}",
                                type='unknown_unit', ref=None,
                                text=text, parent_id=par_id, source_id="",
                                source_file=self.source_file,
                                article_number=article_num,
                                is_amendment_text=True,
                            ))

        walk(article_div)

    def _extract_non_list_table_content(self, table: Tag, parent_id: str,
                                         article_num: str, paragraph_num: Optional[str],
                                         is_amendment: bool = False):
        """Extract text content from non-list table cells."""
        # Determine child type based on parent type (hierarchy rules)
        parent_unit = next((u for u in self.units if u.id == parent_id), None)
        parent_type = parent_unit.type if parent_unit else 'paragraph'
        child_type_map = {
            'paragraph': 'subparagraph',
            'subparagraph': 'point',
            'article': 'point',
            'point': 'subpoint',
            'annex_item': 'subpoint',
            'subpoint': 'subsubpoint',
            'subsubpoint': 'nested_3',
        }
        child_type = child_type_map.get(parent_type, 'subparagraph')
        # Handle deeper nesting
        if parent_type.startswith('nested_'):
            try:
                depth = int(parent_type.split('_')[1]) + 1
                child_type = f'nested_{depth}'
            except (ValueError, IndexError):
                pass

        sub_idx = 0
        for row in table.find_all('tr'):
            for cell in row.find_all(['td', 'th']):
                cell_copy = BeautifulSoup(str(cell), 'lxml').find(['td', 'th']) or cell
                remove_note_tags(cell_copy)
                paragraphs = cell_copy.find_all('p')
                texts = []
                # Extract text from <p> elements
                if paragraphs:
                    for p in paragraphs:
                        t = p.get_text(separator=' ', strip=True)
                        if t and len(t.strip()) >= 10:
                            texts.append(normalize_text(t))
                # Also capture bare text (not inside <p>, <figure>, <table>)
                for p in cell_copy.find_all('p'):
                    p.decompose()
                for fig in cell_copy.find_all('figure'):
                    fig.decompose()
                for tbl in cell_copy.find_all('table'):
                    tbl.decompose()
                bare_text = cell_copy.get_text(separator=' ', strip=True)
                if bare_text and len(bare_text.strip()) >= 10:
                    texts.append(normalize_text(bare_text))
                for t in texts:
                    sub_idx += 1
                    self._add_unit(Unit(
                        id=f"{parent_id}.tbl-{sub_idx}",
                        type=child_type, ref=None,
                        text=t, parent_id=parent_id, source_id="",
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=paragraph_num,
                        is_amendment_text=is_amendment,
                    ))

    def _parse_point_tables(self, tables: list[Tag], parent_id: str, article_num: str,
                           paragraph_num: Optional[str], is_direct: bool = False,
                           depth: int = 0, max_depth: int = 10,
                           is_amendment: bool = False):
        """
        Parse list-tables as points/subpoints.

        depth: 0 = point, 1 = subpoint, 2 = subsubpoint, 3+ = nested_N
        max_depth: safety limit to prevent infinite recursion
        """
        if depth >= max_depth:
            return

        for table in tables:
            if not is_list_table(table):
                # Fallback: extract text from non-list table cells
                self._extract_non_list_table_content(table, parent_id, article_num, paragraph_num,
                                                     is_amendment=is_amendment)
                continue

            # Find tbody first, then rows
            tbody = table.find('tbody', recursive=False)
            if tbody:
                rows = tbody.find_all('tr', recursive=False)
            else:
                rows = table.find_all('tr', recursive=False)

            for row in rows:
                cells = row.find_all('td', recursive=False)
                if len(cells) < 2:
                    continue

                label_cell = cells[0]
                content_cell = cells[1]

                # Get label from <p> element
                label_p = label_cell.find('p', recursive=False)
                if label_p:
                    label_text = label_p.get_text(strip=True)
                else:
                    label_text = label_cell.get_text(strip=True)

                label_normalized, label_type, is_quoted = normalize_label(label_text)

                # Get content (excluding nested tables)
                content_text = get_cell_text(content_cell, exclude_nested_tables=True)
                content_text = normalize_text(content_text)

                # Determine unit type and ID based on depth
                type_names = ['point', 'subpoint', 'subsubpoint']
                id_prefixes = ['pt', 'sub', 'subsub']

                if depth < len(type_names):
                    unit_type = type_names[depth]
                    prefix = id_prefixes[depth]
                else:
                    # For deeper nesting, use nested_N naming
                    unit_type = f'nested_{depth}'
                    prefix = f'n{depth}'

                unit_id = f"{parent_id}.{prefix}-{label_normalized}"

                # Set appropriate label fields
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

                # Parse nested tables recursively
                nested_tables = content_cell.find_all('table', recursive=False)
                if nested_tables:
                    self._parse_point_tables(nested_tables, unit_id, article_num,
                                           paragraph_num, depth=depth+1, max_depth=max_depth,
                                           is_amendment=is_amendment)

                    # Capture ALL non-first <p> in content cell (between and after tables)
                    cont_idx = 0
                    first_p_seen = False
                    for child in content_cell.children:
                        if not isinstance(child, Tag):
                            continue
                        if child.name == 'p':
                            if not first_p_seen:
                                first_p_seen = True
                                continue  # Skip first <p> (already in get_cell_text)
                            p_copy = BeautifulSoup(str(child), 'lxml').find('p') or child
                            remove_note_tags(p_copy)
                            t = p_copy.get_text(separator=' ', strip=True)
                            if t and len(t.strip()) >= 3:
                                cont_idx += 1
                                cont_id = f"{unit_id}.cont-{cont_idx}"
                                next_depth = depth + 1
                                if next_depth < len(type_names):
                                    cont_type = type_names[next_depth]
                                else:
                                    cont_type = f'nested_{next_depth}'
                                self._add_unit(Unit(
                                    id=cont_id, type=cont_type, ref=None,
                                    text=normalize_text(t),
                                    parent_id=unit_id, source_id="",
                                    source_file=self.source_file,
                                    article_number=article_num,
                                    paragraph_number=paragraph_num,
                                    is_amendment_text=is_amendment,
                                ))

                # Capture bare text in content cell (not inside <p>, <figure>, <table>)
                # Handles text alongside formula <figure> elements
                cell_copy = BeautifulSoup(str(content_cell), 'lxml').find('td') or content_cell
                remove_note_tags(cell_copy)
                for tag in cell_copy.find_all(['p', 'figure', 'table', 'div']):
                    tag.decompose()
                bare_text = cell_copy.get_text(separator=' ', strip=True)
                if bare_text and len(bare_text.strip()) >= 10:
                    next_depth = depth + 1
                    if next_depth < len(type_names):
                        bare_type = type_names[next_depth]
                    else:
                        bare_type = f'nested_{next_depth}'
                    self._add_unit(Unit(
                        id=f"{unit_id}.bare-1",
                        type=bare_type, ref=None,
                        text=normalize_text(bare_text),
                        parent_id=unit_id, source_id="",
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=paragraph_num,
                        is_amendment_text=is_amendment,
                    ))

                # Handle nested <div> containers with quoted amendment text
                div_cont_idx = 0
                for div_child in content_cell.find_all('div', recursive=False):
                    for p in div_child.find_all('p', recursive=False):
                        classes = set(p.get('class', []))
                        if classes & {'oj-ti-art', 'oj-sti-art', 'oj-doc-ti'}:
                            continue
                        p_copy = BeautifulSoup(str(p), 'lxml').find('p') or p
                        remove_note_tags(p_copy)
                        t = p_copy.get_text(separator=' ', strip=True)
                        if t and len(t.strip()) >= 10:
                            div_cont_idx += 1
                            next_depth = depth + 1
                            if next_depth < len(type_names):
                                div_type = type_names[next_depth]
                            else:
                                div_type = f'nested_{next_depth}'
                            self._add_unit(Unit(
                                id=f"{unit_id}.div-{div_cont_idx}",
                                type=div_type, ref=None,
                                text=normalize_text(t),
                                parent_id=unit_id, source_id="",
                                source_file=self.source_file,
                                article_number=article_num,
                                paragraph_number=paragraph_num,
                                is_amendment_text=is_amendment,
                            ))

    # -------------------------------------------------------------------------
    # Consolidated Format Parsing
    # -------------------------------------------------------------------------

    def _parse_articles_consolidated(self):
        """Parse articles in consolidated (CELEX) format."""
        article_divs = self.soup.find_all('div', class_='eli-subdivision',
                                          id=lambda x: x and x.startswith('art_'))

        for div in article_divs:
            source_id = div.get('id', '')
            article_num = source_id.replace('art_', '')

            # Get article title (consolidated uses title-article-norm)
            title_p = div.find('p', class_='title-article-norm')
            article_title = title_p.get_text(strip=True) if title_p else f"Article {article_num}"

            # Get article subtitle (if any)
            subtitle = None
            subtitle_p = div.find('p', class_='stitle-article-norm')
            if subtitle_p:
                subtitle = subtitle_p.get_text(strip=True)

            # Create article unit
            article_id = f"art-{article_num}"
            article_unit = Unit(
                id=article_id,
                type='article',
                ref=f"Article {article_num}",
                text="",
                parent_id=None,
                source_id=source_id,
                source_file=self.source_file,
                article_number=article_num,
                heading=subtitle,
            )
            self._add_unit(article_unit)

            # Parse paragraphs (div.norm with span.no-parag)
            self._parse_consolidated_content(div, article_id, article_num)

    def _parse_consolidated_content(self, parent_div: Tag, parent_id: str, article_num: str):
        """Parse content in consolidated format (paragraphs and points)."""
        # Find all direct norm divs (paragraphs)
        intro_idx = 0
        for child in parent_div.children:
            if not isinstance(child, Tag):
                continue

            # Skip title elements
            if 'eli-title' in child.get('class', []):
                continue
            if child.name == 'p' and any(c in child.get('class', []) for c in ['title-article-norm', 'stitle-article-norm']):
                continue

            # Paragraph: <div class="norm"> with <span class="no-parag">
            if child.name == 'div' and 'norm' in child.get('class', []):
                no_parag = child.find('span', class_='no-parag', recursive=False)
                if no_parag:
                    # This is a numbered paragraph
                    par_num_text = no_parag.get_text(strip=True).rstrip('.')
                    # Extract number: "1." -> "1"
                    par_num = re.sub(r'[^\d]', '', par_num_text)

                    par_id = f"{parent_id}.par-{par_num}" if par_num else parent_id

                    # Get paragraph text (from inline-element div)
                    inline_div = child.find('div', class_='inline-element', recursive=False)
                    if inline_div:
                        # Get text excluding nested grid-lists
                        par_text = self._get_consolidated_text(inline_div)
                    else:
                        child_copy = BeautifulSoup(str(child), 'lxml').find('div') or child
                        remove_note_tags(child_copy)
                        par_text = child_copy.get_text(separator=' ', strip=True)
                        # Remove the paragraph number from text
                        par_text = par_text.replace(no_parag.get_text(), '', 1).strip()

                    par_unit = Unit(
                        id=par_id,
                        type='paragraph',
                        ref=f"{par_num}." if par_num else None,
                        text=normalize_text(par_text),
                        parent_id=parent_id,
                        source_id="",
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=par_num,
                    )
                    self._add_unit(par_unit)

                    # Parse points within this paragraph
                    self._parse_consolidated_points(child, par_id, article_num, par_num)

            # Direct grid-list (points without paragraph wrapper)
            elif child.name == 'div' and 'grid-container' in child.get('class', []):
                self._parse_single_grid_point(child, parent_id, article_num, None, depth=0)

            # Intro text followed by points
            elif child.name == 'p' and 'norm' in child.get('class', []):
                # Save intro text as separate unit
                child_copy = BeautifulSoup(str(child), 'lxml').find('p') or child
                remove_note_tags(child_copy)
                intro_text = child_copy.get_text(separator=' ', strip=True)
                if intro_text:
                    intro_idx += 1
                    intro_unit = Unit(
                        id=f"{parent_id}.intro-{intro_idx}",
                        type='intro',
                        ref=None,
                        text=normalize_text(intro_text),
                        parent_id=parent_id,
                        source_id=child.get('id', ''),
                        source_file=self.source_file,
                        article_number=article_num,
                        paragraph_number=None,
                        paragraph_index=None,
                    )
                    self._add_unit(intro_unit)

    def _parse_consolidated_points(self, parent: Tag, parent_id: str, article_num: str,
                                   paragraph_num: Optional[str], depth: int = 0):
        """Parse grid-list points in consolidated format."""
        grid_lists = parent.find_all('div', class_='grid-container', recursive=False)

        # Also check inside inline-element divs
        inline_div = parent.find('div', class_='inline-element', recursive=False)
        if inline_div:
            grid_lists.extend(inline_div.find_all('div', class_='grid-container', recursive=False))

        for grid in grid_lists:
            self._parse_single_grid_point(grid, parent_id, article_num, paragraph_num, depth)

    def _parse_single_grid_point(self, grid: Tag, parent_id: str, article_num: str,
                                  paragraph_num: Optional[str], depth: int):
        """Parse a single grid-container as a point."""
        if depth > 10:
            return

        # Get label from grid-list-column-1
        label_div = grid.find('div', class_='grid-list-column-1')
        if not label_div:
            label_div = grid.find('div', class_='list')
        label_text = ""
        if label_div:
            span = label_div.find('span')
            if span:
                label_text = span.get_text(strip=True)
            else:
                label_text = label_div.get_text(strip=True)

        # Get content from grid-list-column-2
        content_div = grid.find('div', class_='grid-list-column-2')
        content_text = ""
        if content_div:
            # Get text excluding nested grids
            content_text = self._get_consolidated_text(content_div)

        label_normalized, label_type, is_quoted = normalize_label(label_text)

        # Determine unit type based on depth
        type_names = ['point', 'subpoint', 'subsubpoint']
        id_prefixes = ['pt', 'sub', 'subsub']

        if depth < len(type_names):
            unit_type = type_names[depth]
            prefix = id_prefixes[depth]
        else:
            unit_type = f'nested_{depth}'
            prefix = f'n{depth}'

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

        # Parse nested points
        if content_div:
            nested_grids = content_div.find_all('div', class_='grid-container', recursive=False)
            for nested in nested_grids:
                self._parse_single_grid_point(nested, unit_id, article_num, paragraph_num, depth + 1)

    def _get_consolidated_text(self, element: Tag) -> str:
        """Get text from consolidated element, excluding nested grid-lists."""
        # Clone to avoid modifying original
        clone = BeautifulSoup(str(element), 'lxml')
        root = clone.find('div') or clone.find('p') or clone
        remove_note_tags(root)

        # Remove nested grid-containers
        for grid in root.find_all('div', class_='grid-container'):
            grid.decompose()

        # Get text from p.norm elements or direct text
        texts = []
        for p in root.find_all('p', class_='norm'):
            remove_note_tags(p)
            text = p.get_text(separator=' ', strip=True)
            if text:
                texts.append(text)

        if texts:
            return ' '.join(texts)

        return root.get_text(separator=' ', strip=True)

    # -------------------------------------------------------------------------
    # Annex Parsing
    # -------------------------------------------------------------------------

    def _parse_annexes(self):
        """Parse all annexes."""
        annex_divs = self.soup.find_all('div', class_='eli-container',
                                        id=lambda x: x and x.strip().startswith('anx_'))

        for div in annex_divs:
            source_id = div.get('id', '').strip()
            # Handle ids like "anx_ I" (with space)
            annex_num = source_id.replace('anx_', '').strip()

            # Get annex title
            title_p = div.find('p', class_='oj-doc-ti')
            annex_title = title_p.get_text(strip=True) if title_p else f"ANNEX {annex_num}"

            # Get annex subtitle/heading
            heading_p = div.find('p', class_='oj-ti-grseq-1')
            heading = None
            if heading_p:
                heading = heading_p.get_text(strip=True)

            annex_id = f"annex-{annex_num}"
            annex_unit = Unit(
                id=annex_id,
                type='annex',
                ref=f"ANNEX {annex_num}",
                text="",
                parent_id=None,
                source_id=source_id,
                source_file=self.source_file,
                annex_number=annex_num,
                heading=heading or annex_title,
            )
            self._add_unit(annex_unit)

            # Parse annex content - look for parts first
            self._parse_annex_content(div, annex_id, annex_num)

    def _parse_annex_content(self, annex_div: Tag, annex_id: str, annex_num: str):
        """Parse content within an annex."""
        current_part = None
        current_parent_id = annex_id
        annex_item_idx = 0

        # Process all direct children
        for child in annex_div.children:
            if not isinstance(child, Tag):
                continue

            # Check for part headers
            if child.name == 'p' and 'oj-ti-grseq-1' in child.get('class', []):
                text = child.get_text(strip=True)
                if text.lower().startswith('part '):
                    # Extract part identifier
                    m = re.match(r'Part\s+([A-Z])', text, re.IGNORECASE)
                    if m:
                        current_part = m.group(1).upper()
                        part_id = f"{annex_id}.part-{current_part}"
                        part_unit = Unit(
                            id=part_id,
                            type='annex_part',
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

            # Parse tables as list items
            elif child.name == 'table' and is_list_table(child):
                rows = child.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        label_text = get_cell_text(cells[0]).strip()
                        content_text = get_cell_text(cells[1], exclude_nested_tables=True)

                        label_normalized, label_type, is_quoted = normalize_label(label_text)

                        item_id = f"{current_parent_id}.item-{label_normalized}"
                        item_unit = Unit(
                            id=item_id,
                            type='annex_item',
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

                        # Parse nested tables
                        nested_tables = cells[1].find_all('table', recursive=False)
                        if nested_tables:
                            self._parse_point_tables(nested_tables, item_id, None, None, depth=1)

            # Non-list data table — extract per-cell, per-paragraph text
            elif child.name == 'table' and not is_list_table(child):
                for row in child.find_all('tr'):
                    for cell in row.find_all(['td', 'th']):
                        cell_copy = BeautifulSoup(str(cell), 'lxml').find(['td', 'th']) or cell
                        remove_note_tags(cell_copy)
                        # Extract from direct <p> children first
                        direct_paragraphs = cell_copy.find_all('p', recursive=False)
                        if direct_paragraphs:
                            for p in direct_paragraphs:
                                t = p.get_text(separator=' ', strip=True)
                                if t and len(t.strip()) >= 5:
                                    annex_item_idx += 1
                                    self._add_unit(Unit(
                                        id=f"{current_parent_id}.item-{annex_item_idx}",
                                        type='annex_item', ref=None,
                                        text=normalize_text(t),
                                        parent_id=current_parent_id, source_id="",
                                        source_file=self.source_file,
                                        annex_number=annex_num, annex_part=current_part,
                                    ))
                        # Also capture bare text (not inside <p>, <figure>, <table>)
                        for p_tag in cell_copy.find_all('p'):
                            p_tag.decompose()
                        for fig in cell_copy.find_all('figure'):
                            fig.decompose()
                        for tbl in cell_copy.find_all('table'):
                            tbl.decompose()
                        bare_t = cell_copy.get_text(separator=' ', strip=True)
                        if bare_t and len(bare_t.strip()) >= 5:
                            annex_item_idx += 1
                            self._add_unit(Unit(
                                id=f"{current_parent_id}.item-{annex_item_idx}",
                                type='annex_item', ref=None,
                                text=normalize_text(bare_t),
                                parent_id=current_parent_id, source_id="",
                                source_file=self.source_file,
                                annex_number=annex_num, annex_part=current_part,
                            ))

            # Content paragraphs (not headings)
            elif child.name == 'p':
                classes = child.get('class', [])
                if any(c in classes for c in ('oj-doc-ti', 'oj-ti-grseq-1')):
                    continue
                p_copy = BeautifulSoup(str(child), 'lxml').find('p') or child
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=' ', strip=True)
                if text and len(text.strip()) >= 5:
                    annex_item_idx += 1
                    self._add_unit(Unit(
                        id=f"{current_parent_id}.item-{annex_item_idx}",
                        type='annex_item', ref=None,
                        text=normalize_text(text),
                        parent_id=current_parent_id, source_id="",
                        source_file=self.source_file,
                        annex_number=annex_num, annex_part=current_part,
                    ))

            # Enumeration-spacing divs (Prospectus-style annexes)
            elif child.name == 'div' and 'oj-enumeration-spacing' in child.get('class', []):
                div_copy = BeautifulSoup(str(child), 'lxml').find('div') or child
                remove_note_tags(div_copy)
                text = div_copy.get_text(separator=' ', strip=True)
                if text and len(text.strip()) >= 5:
                    annex_item_idx += 1
                    self._add_unit(Unit(
                        id=f"{current_parent_id}.item-{annex_item_idx}",
                        type='annex_item', ref=None,
                        text=normalize_text(text),
                        parent_id=current_parent_id, source_id="",
                        source_file=self.source_file,
                        annex_number=annex_num, annex_part=current_part,
                    ))

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate(self):
        """Run validation checks."""
        # Check for orphans (units with parent_id that doesn't exist)
        all_ids = {u.id for u in self.units}
        for unit in self.units:
            if unit.parent_id and unit.parent_id not in all_ids:
                self.validation.orphans.append({
                    'id': unit.id,
                    'parent_id': unit.parent_id,
                })

        # Check sequence gaps for recitals
        recital_nums = sorted([
            int(u.recital_number) for u in self.units
            if u.type == 'recital' and u.recital_number and u.recital_number.isdigit()
        ])
        if recital_nums:
            expected = set(range(1, max(recital_nums) + 1))
            actual = set(recital_nums)
            gaps = expected - actual
            if gaps:
                self.validation.sequence_gaps.append({
                    'type': 'recital',
                    'missing': sorted(gaps)
                })


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Parse EU Official Journal HTML files to JSON'
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to input HTML file'
    )
    parser.add_argument(
        '--out', '-o',
        help='Path to output JSON file (default: out/json/<name>.json)'
    )
    parser.add_argument(
        '--validation', '-v',
        nargs='?',
        const=True,
        default=True,
        help='Path to validation report JSON file (default: out/validation/<name>_validation.json)'
    )
    parser.add_argument(
        '--no-validation',
        action='store_true',
        help='Disable validation report generation'
    )
    parser.add_argument(
        '--out-dir',
        default='out',
        help='Base output directory (default: out)'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run coverage test after parsing'
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    base_name = input_path.stem
    out_dir = Path(args.out_dir)

    # Determine output paths
    if args.out:
        output_path = Path(args.out)
    else:
        output_path = out_dir / 'json' / f'{base_name}.json'

    # Determine validation path
    if args.no_validation:
        validation_path = None
    elif args.validation is True:
        validation_path = out_dir / 'validation' / f'{base_name}_validation.json'
    elif args.validation:
        validation_path = Path(args.validation)
    else:
        validation_path = None

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Read HTML
    with open(input_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Parse
    eu_parser = EUParser(source_file=str(input_path))
    units = eu_parser.parse(html_content)

    # Convert to dict for JSON serialization
    units_data = [asdict(u) for u in units]

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(units_data, f, ensure_ascii=False, indent=2)

    print(f"Parsed {len(units)} units -> {output_path}")

    # Write validation report if requested
    if validation_path:
        validation_path.parent.mkdir(parents=True, exist_ok=True)
        with open(validation_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(eu_parser.validation), f, ensure_ascii=False, indent=2)

        status = "PASS" if eu_parser.validation.is_valid() else "ISSUES FOUND"
        print(f"Validation: {status} -> {validation_path}")

    # Print summary
    print("\nSummary:")
    for unit_type, count in sorted(eu_parser.validation.counts_parsed.items()):
        print(f"  {unit_type}: {count}")

    # Run coverage test if requested
    if args.coverage:
        print("\n" + "="*60)
        print("Running coverage test...")
        print("="*60)
        try:
            from test_coverage import coverage_test, validate_hierarchy, print_report
            report = coverage_test(input_path, output_path)
            hierarchy = validate_hierarchy(units_data)
            passed = print_report(report, hierarchy, verbose=False)
            if not passed:
                sys.exit(1)
        except ImportError as e:
            print(f"Warning: Could not run coverage test: {e}", file=sys.stderr)


if __name__ == '__main__':
    main()
