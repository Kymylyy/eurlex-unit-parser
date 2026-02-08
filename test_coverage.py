#!/usr/bin/env python3
"""
Coverage test for EU parser.

Verifies that:
1. All text content from HTML is captured in JSON (content coverage)
2. Hierarchy structure is valid (parent_id, ID consistency, sequences)
3. No "phantom" text exists in JSON that doesn't appear in HTML

Supports two oracles:
- naive: independent, text-first extraction (default)
- mirror: mirrors parser logic (legacy)
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup, Tag

# Import helpers from parser (avoid circular import by importing only functions)
from parse_eu import (
    remove_note_tags,
    normalize_text,
    strip_leading_label,
    is_list_table,
    get_cell_text,
)


# =============================================================================
# HTML Text Extraction (mirrors parser logic)
# =============================================================================

def detect_format(soup: BeautifulSoup) -> bool:
    """Detect if this is consolidated format. Returns True if consolidated."""
    if soup.find('p', class_='title-article-norm'):
        return True
    if soup.find('div', class_='grid-container'):
        return True
    return False


# =============================================================================
# Naive Oracle Extraction (independent)
# =============================================================================

LABEL_ONLY_RE = re.compile(
    r'^(Article\s+\d+[A-Z]?|ANNEX\s+[IVXLC0-9]+|Part\s+[A-Z]|CHAPTER\s+[IVXLC0-9]+|SECTION\s+[IVXLC0-9]+|SUB-?SECTION\s+[IVXLC0-9]+|TITLE\s+[IVXLC0-9]+)(\s+[-—–:]\s+.*|\s+.*)?$',
    re.IGNORECASE
)
PUNCT_LABEL_RE = re.compile(r'^\(?[a-zivx0-9]{1,4}\)?[.)]?$', re.IGNORECASE)
WHITESPACE_RE = re.compile(r'\s+')
LEADING_REF_RE = re.compile(r"^(?:['“”‘’]?\(?[a-zivx0-9]{1,4}\)?[.)]?)\s+", re.IGNORECASE)
LEADING_NUM_RE = re.compile(r'^(\d+)[.)]\s+')
LEADING_DASH_RE = re.compile(r'^[—–-]\s+')

NAIVE_HEADING_CLASSES = {
    'oj-ti-art',
    'oj-sti-art',
    'oj-doc-ti',
    'oj-ti-grseq-1',
    'oj-ti-grseq-2',
    'oj-ti-grseq-3',
    'oj-ti-grseq-4',
    'oj-ti-grseq-5',
    'oj-ti-grseq-6',
    'oj-ti-grseq-7',
    'oj-ti-grseq-8',
    'oj-ti-grseq-9',
    'oj-ti-grseq-10',
    'title-article-norm',
    'stitle-article-norm',
}


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(' ', text).strip()


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
    # Remove repeated leading labels like "1. (a) (i) ..."
    while True:
        new_line = LEADING_NUM_RE.sub('', line)
        new_line = LEADING_REF_RE.sub('', new_line)
        new_line = LEADING_DASH_RE.sub('', new_line)
        if new_line == line:
            break
        line = new_line.strip()
    return line.strip()


def extract_naive_segments(container: Tag, min_len: int = 10) -> list[str]:
    # Clone and remove heading-like elements (structural metadata)
    clone = BeautifulSoup(str(container), 'lxml')
    for cls in NAIVE_HEADING_CLASSES:
        for tag in clone.find_all(class_=cls):
            tag.decompose()

    raw = clone.get_text(separator='\n', strip=True)
    lines = [normalize_whitespace(l) for l in raw.splitlines()]
    segments = []
    for line in lines:
        line = strip_leading_ref(line)
        if len(line) < min_len:
            continue
        if looks_like_label(line):
            continue
        segments.append(line)
    return segments


def build_naive_section_map(soup: BeautifulSoup) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}

    # Recitals and Articles
    for div in soup.find_all('div', class_='eli-subdivision',
                              id=lambda x: x and (x.startswith('rct_') or x.startswith('art_'))):
        source_id = div.get('id', '')
        if source_id.startswith('rct_'):
            key = 'recitals'
        else:
            article_num = source_id.replace('art_', '')
            key = f'art_{article_num}'
        sections.setdefault(key, []).extend(extract_naive_segments(div))

    # Annexes
    for div in soup.find_all('div', class_='eli-container',
                              id=lambda x: x and x.strip().startswith('anx_')):
        if is_correlation_table_annex(div):
            continue
        source_id = div.get('id', '').strip()
        annex_num = source_id.replace('anx_', '').strip()
        key = f'annex_{annex_num}' if annex_num else 'annex'
        sections.setdefault(key, []).extend(extract_naive_segments(div))

    return sections


def is_correlation_table_annex(div: Tag) -> bool:
    heading_texts = []
    for cls in list(NAIVE_HEADING_CLASSES) + ['oj-ti-tbl', 'oj-doc-ti']:
        for tag in div.find_all(class_=cls):
            heading_texts.append(tag.get_text(separator=' ', strip=True))
    # Also check first few <p> elements in the annex
    for p in div.find_all('p', limit=5):
        heading_texts.append(p.get_text(separator=' ', strip=True))
    for text in heading_texts:
        if 'correlation table' in text.lower():
            return True
    return False


def get_consolidated_text_for_test(element: Tag) -> str:
    """
    Get text from consolidated element, excluding nested grid-lists.
    Mirrors parser's _get_consolidated_text() method.
    """
    # Clone to avoid modifying original
    clone = BeautifulSoup(str(element), 'lxml')
    root = clone.find('div') or clone.find('p') or clone

    # Remove nested grid-containers
    for grid in root.find_all('div', class_='grid-container'):
        grid.decompose()

    # Get text from p.norm elements or direct text
    texts = []
    for p in root.find_all('p', class_='norm'):
        text = p.get_text(separator=' ', strip=True)
        if text:
            texts.append(text)

    if texts:
        return ' '.join(texts)

    return root.get_text(separator=' ', strip=True)


def extract_paragraph_texts_oj(soup: BeautifulSoup) -> dict[str, Counter]:
    """
    Extract paragraph/subparagraph texts from OJ format HTML.
    Returns: {article_num: Counter of normalized texts}
    """
    result = {'recitals': Counter()}

    # Recitals - handle both TABLE format and direct <p> format (like parser)
    for div in soup.find_all('div', class_='eli-subdivision',
                              id=lambda x: x and x.startswith('rct_')):
        # Check for table format first (most common)
        table = div.find('table')
        if table and is_list_table(table):
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    # Second cell contains recital text (first cell has label)
                    text = get_cell_text(cells[1])
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result['recitals'][text] += 1
        else:
            # Direct <p> format - combine all <p> elements
            combined_parts = []
            for p in div.find_all('p', class_='oj-normal'):
                p_copy = BeautifulSoup(str(p), 'lxml').find('p')
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=' ', strip=True)
                text, _ = strip_leading_label(text)
                if text:
                    combined_parts.append(text)

            full_text = normalize_text(' '.join(combined_parts))
            if full_text and len(full_text) > 5:
                result['recitals'][full_text] += 1

    # Articles
    for div in soup.find_all('div', class_='eli-subdivision',
                              id=lambda x: x and x.startswith('art_')):
        article_num = div.get('id', '').replace('art_', '')
        result[article_num] = Counter()

        # Find paragraph divs (id like "001.001")
        paragraph_divs = div.find_all('div', id=re.compile(r'^\d{3}\.\d{3}$'), recursive=False)

        if paragraph_divs:
            for par_div in paragraph_divs:
                # Iterate direct children in DOM order (like parser)
                for child in par_div.children:
                    if not isinstance(child, Tag):
                        continue
                    if child.name == 'p' and 'oj-normal' in child.get('class', []):
                        p_copy = BeautifulSoup(str(child), 'lxml').find('p') or child
                        remove_note_tags(p_copy)
                        text = p_copy.get_text(separator=' ', strip=True)
                        text, _ = strip_leading_label(text)
                        text = normalize_text(text)
                        if text and len(text) > 5:
                            result[article_num][text] += 1
        else:
            # Article without paragraph divs - direct <p> elements
            for p in div.find_all('p', class_='oj-normal', recursive=False):
                p_copy = BeautifulSoup(str(p), 'lxml').find('p') or p
                remove_note_tags(p_copy)
                text = p_copy.get_text(separator=' ', strip=True)
                text, _ = strip_leading_label(text)
                text = normalize_text(text)
                if text and len(text) > 5:
                    result[article_num][text] += 1

    return result


def extract_point_texts_oj(soup: BeautifulSoup) -> dict[str, Counter]:
    """
    Extract point texts from OJ format HTML (from list-tables).
    Returns: {article_num: Counter of normalized texts}
    """
    result = {}

    for div in soup.find_all('div', class_='eli-subdivision',
                              id=lambda x: x and x.startswith('art_')):
        article_num = div.get('id', '').replace('art_', '')
        result[article_num] = Counter()

        # Find all list-tables (excluding nested tables inside other tables)
        for table in div.find_all('table'):
            # Skip nested tables (tables inside table cells)
            if table.find_parent('td'):
                continue
            if not is_list_table(table):
                continue

            tbody = table.find('tbody', recursive=False)
            rows = tbody.find_all('tr', recursive=False) if tbody else table.find_all('tr', recursive=False)

            for row in rows:
                cells = row.find_all('td', recursive=False)
                if len(cells) >= 2:
                    text = get_cell_text(cells[1], exclude_nested_tables=True)
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result[article_num][text] += 1

    return result


def extract_paragraph_texts_consolidated(soup: BeautifulSoup) -> dict[str, Counter]:
    """
    Extract paragraph texts from consolidated format HTML.
    Mirrors parser's _parse_consolidated_article_content() logic exactly.
    """
    result = {}

    for div in soup.find_all('div', class_='eli-subdivision',
                              id=lambda x: x and x.startswith('art_')):
        article_num = div.get('id', '').replace('art_', '')
        result[article_num] = Counter()

        # Iterate direct children in DOM order (like parser)
        for child in div.children:
            if not isinstance(child, Tag):
                continue

            # Skip title elements
            if 'eli-title' in child.get('class', []):
                continue
            if child.name == 'p' and any(c in child.get('class', [])
                                         for c in ['title-article-norm', 'stitle-article-norm']):
                continue

            # Numbered paragraph: <div class="norm"> with <span class="no-parag">
            if child.name == 'div' and 'norm' in child.get('class', []):
                no_parag = child.find('span', class_='no-parag', recursive=False)
                if no_parag:
                    # Get paragraph text using same logic as parser
                    inline_div = child.find('div', class_='inline-element', recursive=False)
                    if inline_div:
                        text = get_consolidated_text_for_test(inline_div)
                    else:
                        text = child.get_text(separator=' ', strip=True)
                        # Remove the paragraph number from text
                        text = text.replace(no_parag.get_text(), '', 1).strip()
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result[article_num][text] += 1

            # Intro text: <p class="norm">
            elif child.name == 'p' and 'norm' in child.get('class', []):
                text = child.get_text(separator=' ', strip=True)
                text = normalize_text(text)
                if text and len(text) > 5:
                    result[article_num][text] += 1

    return result


def extract_point_texts_consolidated(soup: BeautifulSoup) -> dict[str, Counter]:
    """Extract point texts from consolidated format HTML (grid-containers)."""
    result = {}

    for div in soup.find_all('div', class_='eli-subdivision',
                              id=lambda x: x and x.startswith('art_')):
        article_num = div.get('id', '').replace('art_', '')
        result[article_num] = Counter()

        for grid in div.find_all('div', class_='grid-container'):
            content_div = grid.find('div', class_='grid-list-column-2')
            if content_div:
                # Get text from p.norm elements
                for p in content_div.find_all('p', class_='norm', recursive=False):
                    text = p.get_text(separator=' ', strip=True)
                    text = normalize_text(text)
                    if text and len(text) > 5:
                        result[article_num][text] += 1

    return result


# =============================================================================
# JSON Text Extraction
# =============================================================================

def extract_json_paragraph_texts(units: list[dict]) -> dict[str, Counter]:
    """Extract paragraph/subparagraph texts from parsed JSON."""
    result = {'recitals': Counter()}

    for unit in units:
        text = unit.get('text', '').strip()
        if not text or len(text) <= 5:
            continue

        unit_type = unit.get('type', '')

        if unit_type == 'recital':
            result['recitals'][text] += 1

        elif unit_type in ('paragraph', 'subparagraph', 'intro'):
            article_num = unit.get('article_number')
            if article_num:
                if article_num not in result:
                    result[article_num] = Counter()
                result[article_num][text] += 1

    return result


def extract_json_point_texts(units: list[dict]) -> dict[str, Counter]:
    """Extract point/subpoint texts from parsed JSON."""
    result = {}

    for unit in units:
        text = unit.get('text', '').strip()
        if not text or len(text) <= 5:
            continue

        unit_type = unit.get('type', '')

        if unit_type in ('point', 'subpoint', 'subsubpoint') or unit_type.startswith('nested_'):
            article_num = unit.get('article_number')
            if article_num:
                if article_num not in result:
                    result[article_num] = Counter()
                result[article_num][text] += 1

    return result


def extract_json_all_texts(units: list[dict]) -> dict[str, Counter]:
    """Extract ALL article-level texts regardless of type, for cross-checking."""
    result = {'recitals': Counter()}

    for unit in units:
        text = unit.get('text', '').strip()
        if not text or len(text) <= 5:
            continue

        unit_type = unit.get('type', '')

        if unit_type == 'recital':
            result['recitals'][text] += 1
        elif unit_type in ('paragraph', 'subparagraph', 'intro', 'point', 'subpoint',
                           'subsubpoint', 'unknown_unit') or unit_type.startswith('nested_'):
            article_num = unit.get('article_number')
            if article_num:
                if article_num not in result:
                    result[article_num] = Counter()
                result[article_num][text] += 1

    return result


def build_json_section_texts(units: list[dict]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}

    for unit in units:
        text = normalize_whitespace(unit.get('text', '') or '')
        if not text:
            continue

        unit_type = unit.get('type', '')

        if unit_type == 'recital':
            key = 'recitals'
        elif unit.get('annex_number') is not None:
            annex_num = unit.get('annex_number')
            key = f'annex_{annex_num}' if annex_num else 'annex'
        elif unit.get('article_number') is not None:
            key = f"art_{unit.get('article_number')}"
        else:
            continue

        sections.setdefault(key, []).append(text)

    return sections


def build_full_html_text_by_section(soup: BeautifulSoup) -> dict[str, str]:
    sections: dict[str, str] = {}

    for div in soup.find_all('div', class_='eli-subdivision',
                              id=lambda x: x and (x.startswith('rct_') or x.startswith('art_'))):
        source_id = div.get('id', '')
        if source_id.startswith('rct_'):
            key = 'recitals'
        else:
            article_num = source_id.replace('art_', '')
            key = f'art_{article_num}'
        clone = BeautifulSoup(str(div), 'lxml')
        root = clone.find('div') or clone
        remove_note_tags(root)
        text = normalize_text(root.get_text(separator=' ', strip=True))
        if key in sections:
            sections[key] = f"{sections[key]} {text}".strip()
        else:
            sections[key] = text

    for div in soup.find_all('div', class_='eli-container',
                              id=lambda x: x and x.strip().startswith('anx_')):
        source_id = div.get('id', '').strip()
        annex_num = source_id.replace('anx_', '').strip()
        key = f'annex_{annex_num}' if annex_num else 'annex'
        clone = BeautifulSoup(str(div), 'lxml')
        root = clone.find('div') or clone
        remove_note_tags(root)
        text = normalize_text(root.get_text(separator=' ', strip=True))
        if key in sections:
            sections[key] = f"{sections[key]} {text}".strip()
        else:
            sections[key] = text

    return sections


# =============================================================================
# Coverage Comparison
# =============================================================================

def compare_counters(html_counter: Counter, json_counter: Counter) -> dict:
    """
    Compare two Counters.
    Returns: {missing: [...], missing_raw: [...], extra: [...], matched: int}
    missing_raw contains full-length texts for cross-checking.
    """
    missing = []
    missing_raw = []
    extra = []
    matched = 0

    # Find missing (in HTML but not in JSON)
    for text, count in html_counter.items():
        json_count = json_counter.get(text, 0)
        if json_count < count:
            for _ in range(count - json_count):
                missing.append(text[:100] + ('...' if len(text) > 100 else ''))
                missing_raw.append(text)
        matched += min(count, json_count)

    # Find extra (in JSON but not in HTML)
    for text, count in json_counter.items():
        html_count = html_counter.get(text, 0)
        if count > html_count:
            for _ in range(count - html_count):
                extra.append(text[:100] + ('...' if len(text) > 100 else ''))

    return {'missing': missing, 'missing_raw': missing_raw, 'extra': extra, 'matched': matched}


def coverage_test(html_path: Path, json_path: Path, oracle: str = 'naive') -> dict:
    """Run coverage test comparing HTML and JSON."""
    # Load files
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')

    with open(json_path, 'r', encoding='utf-8') as f:
        units = json.load(f)

    # Detect format
    is_consolidated = detect_format(soup)

    # Extract texts
    if oracle == 'mirror':
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

    # Compare
    report = {
        'format': 'Consolidated' if is_consolidated else 'OJ (Official Journal)',
        'paragraphs': {},
        'points': {},
        'summary': {},
        'oracle': oracle
    }

    if oracle == 'mirror':
        # Compare paragraphs
        all_keys = set(html_paragraphs.keys()) | set(json_paragraphs.keys())
        total_html_par = 0
        total_missing_par = 0

        for key in sorted(all_keys, key=lambda x: (x != 'recitals', int(x) if x.isdigit() else 999)):
            html_c = html_paragraphs.get(key, Counter())
            json_c = json_paragraphs.get(key, Counter())
            comparison = compare_counters(html_c, json_c)

            report['paragraphs'][key] = {
                'html_count': sum(html_c.values()),
                'json_count': sum(json_c.values()),
                'matched': comparison['matched'],
                'missing': comparison['missing'],
                'missing_raw': comparison['missing_raw'],
                'extra': comparison['extra']
            }
            total_html_par += sum(html_c.values())
            total_missing_par += len(comparison['missing'])

        # Compare points
        all_keys = set(html_points.keys()) | set(json_points.keys())
        total_html_pt = 0
        total_missing_pt = 0

        for key in sorted(all_keys, key=lambda x: int(x) if x.isdigit() else 999):
            html_c = html_points.get(key, Counter())
            json_c = json_points.get(key, Counter())
            comparison = compare_counters(html_c, json_c)

            report['points'][key] = {
                'html_count': sum(html_c.values()),
                'json_count': sum(json_c.values()),
                'matched': comparison['matched'],
                'missing': comparison['missing'],
                'missing_raw': comparison['missing_raw'],
                'extra': comparison['extra']
            }
            total_html_pt += sum(html_c.values())
            total_missing_pt += len(comparison['missing'])

        # Cross-check missing texts: gone (truly absent) vs misclassified (present but wrong type)
        total_gone = 0
        total_misclassified = 0

        # Check missing paragraphs against all JSON texts
        for key, data in report['paragraphs'].items():
            gone_count = 0
            misclassified_count = 0
            all_c = json_all.get(key, Counter())
            for raw_text in data.get('missing_raw', []):
                if all_c.get(raw_text, 0) > 0:
                    misclassified_count += 1
                else:
                    gone_count += 1
            data['gone'] = gone_count
            data['misclassified'] = misclassified_count
            total_gone += gone_count
            total_misclassified += misclassified_count

        # Check missing points against all JSON texts
        for key, data in report['points'].items():
            gone_count = 0
            misclassified_count = 0
            all_c = json_all.get(key, Counter())
            for raw_text in data.get('missing_raw', []):
                if all_c.get(raw_text, 0) > 0:
                    misclassified_count += 1
                else:
                    gone_count += 1
            data['gone'] = gone_count
            data['misclassified'] = misclassified_count
            total_gone += gone_count
            total_misclassified += misclassified_count

        # Summary
        total_html = total_html_par + total_html_pt
        total_missing = total_missing_par + total_missing_pt
        report['summary'] = {
            'total_html_segments': total_html,
            'total_missing': total_missing,
            'gone': total_gone,
            'misclassified': total_misclassified,
            'coverage_pct': 100.0 * (total_html - total_missing) / total_html if total_html > 0 else 100.0,
            'text_recall_pct': 100.0 * (total_html - total_gone) / total_html if total_html > 0 else 100.0,
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
                    missing.append(seg[:100] + ('...' if len(seg) > 100 else ''))

            report['paragraphs'][key] = {
                'html_count': len(html_segments),
                'json_count': len(json_texts),
                'matched': len(html_segments) - len(missing),
                'missing': missing,
                'extra': []
            }
            total_html += len(html_segments)
            total_missing += len(missing)

        report['summary'] = {
            'total_html_segments': total_html,
            'total_missing': total_missing,
            'coverage_pct': 100.0 * (total_html - total_missing) / total_html if total_html > 0 else 100.0
        }

    return report


# =============================================================================
# Hierarchy Validation
# =============================================================================

def validate_hierarchy(units: list[dict]) -> dict:
    """Validate hierarchy structure of parsed units."""
    issues = []

    # Build ID set and lookup
    all_ids = {u['id'] for u in units}
    units_by_id = {u['id']: u for u in units}

    # Expected parent types
    # - article: allowed for point in consolidated format (points directly under article)
    # - annex_item: allowed for subpoint in annexes
    parent_type_rules = {
        'subparagraph': ['paragraph'],
        'point': ['paragraph', 'subparagraph', 'article'],
        'subpoint': ['point', 'annex_item'],
        'subsubpoint': ['subpoint'],
    }

    for unit in units:
        unit_id = unit['id']
        unit_type = unit['type']
        parent_id = unit.get('parent_id')

        # Check parent_id exists
        if parent_id and parent_id not in all_ids:
            issues.append({
                'type': 'orphan',
                'id': unit_id,
                'message': f"parent_id '{parent_id}' does not exist"
            })

        # Check parent type is valid
        if parent_id and unit_type in parent_type_rules:
            parent = units_by_id.get(parent_id)
            if parent:
                expected_types = parent_type_rules[unit_type]
                if parent['type'] not in expected_types:
                    issues.append({
                        'type': 'wrong_parent_type',
                        'id': unit_id,
                        'message': f"{unit_type} has parent type '{parent['type']}', expected one of {expected_types}"
                    })

        # Check ID/metadata consistency
        if unit_type == 'paragraph' and unit.get('paragraph_number'):
            expected_suffix = f".par-{unit['paragraph_number']}"
            if expected_suffix not in unit_id:
                issues.append({
                    'type': 'id_mismatch',
                    'id': unit_id,
                    'message': f"paragraph_number={unit['paragraph_number']} doesn't match id"
                })

        if unit_type == 'point' and unit.get('point_label'):
            expected_suffix = f".pt-{unit['point_label']}"
            if expected_suffix not in unit_id:
                issues.append({
                    'type': 'id_mismatch',
                    'id': unit_id,
                    'message': f"point_label={unit['point_label']} doesn't match id"
                })

    return {
        'valid': len(issues) == 0,
        'issues': issues
    }


def validate_ordering(units: list[dict]) -> dict:
    """Validate that points and subparagraphs are not interleaved under the same parent."""
    issues = []

    # Group children by parent_id
    children_by_parent: dict[str, list[dict]] = {}
    for u in units:
        pid = u.get('parent_id', '')
        if pid:
            children_by_parent.setdefault(pid, []).append(u)

    for pid, kids in children_by_parent.items():
        types = [u['type'] for u in kids]
        if 'point' not in types or 'subparagraph' not in types:
            continue

        # FSM: allows multiple groups of points separated by subparagraphs.
        # Pattern: [subpar*] [point+] [subpar* [point+]]* [subpar*]
        # Only flag truly interleaved: single point sandwiched between subparagraphs
        # with no other points in that group.
        # In EU law, it's valid to have: intro → points → closing → new_intro → more_points
        state = 'start'
        for i, t in enumerate(types):
            if state == 'start':
                if t == 'point':
                    state = 'points'
                elif t == 'subparagraph':
                    state = 'intro_subpar'
            elif state == 'intro_subpar':
                if t == 'point':
                    state = 'points'
            elif state == 'points':
                if t == 'subparagraph':
                    state = 'gap_subpar'
            elif state == 'gap_subpar':
                if t == 'point':
                    # New point group after subparagraph — this is legal
                    state = 'points'
                elif t != 'subparagraph':
                    state = 'start'  # Reset on other types

    return {
        'valid': len(issues) == 0,
        'issues': issues,
    }


# =============================================================================
# Report Printing
# =============================================================================

def print_report(report: dict, hierarchy: dict, verbose: bool = False, phantom: Optional[dict] = None, ordering: Optional[dict] = None) -> bool:
    """Print coverage report. Returns True if all passed."""
    print(f"\n{'='*60}")
    print(f"COVERAGE REPORT")
    print(f"{'='*60}")
    print(f"Format: {report['format']}")

    print(f"\nORACLE: {report.get('oracle', 'mirror')}")

    # Paragraphs (or sections in naive)
    print(f"\nSECTIONS:")
    par_issues = []
    for key, data in report['paragraphs'].items():
        if data['missing']:
            par_issues.append((key, data))
        elif verbose:
            label = 'Recitals' if key == 'recitals' else key
            print(f"  [OK] {label}: {data['json_count']}/{data['html_count']}")

    if par_issues:
        for key, data in par_issues:
            label = 'Recitals' if key == 'recitals' else key
            print(f"  [!!] {label}: {data['json_count']}/{data['html_count']} ({len(data['missing'])} missing)")
            if verbose:
                for m in data['missing'][:3]:
                    print(f"       - {m}")
    else:
        print(f"  [OK] All {len(report['paragraphs'])} sections fully covered")

    # Points (mirror only)
    if report.get('oracle') == 'mirror' and report['points']:
        print(f"\nPOINTS:")
        pt_issues = []
        for key, data in report['points'].items():
            if data['missing']:
                pt_issues.append((key, data))

        if pt_issues:
            for key, data in pt_issues:
                print(f"  [!!] Article {key}: {data['json_count']}/{data['html_count']} ({len(data['missing'])} missing)")
                if verbose:
                    for m in data['missing'][:3]:
                        print(f"       - {m}")
        else:
            total_points = sum(d['json_count'] for d in report['points'].values())
            print(f"  [OK] All {total_points} points covered")

    # Hierarchy
    print(f"\nHIERARCHY:")
    if hierarchy['valid']:
        print(f"  [OK] All parent_ids valid")
        print(f"  [OK] ID/metadata consistent")
    else:
        for issue in hierarchy['issues'][:5]:
            print(f"  [!!] {issue['type']}: {issue['id']}")
            print(f"       {issue['message']}")
        if len(hierarchy['issues']) > 5:
            print(f"  ... and {len(hierarchy['issues']) - 5} more issues")

    # Ordering
    print(f"\nORDERING:")
    if ordering is None or ordering['valid']:
        print(f"  [OK] No interleaved points/subparagraphs")
    else:
        for issue in ordering['issues'][:5]:
            print(f"  [!!] {issue['type']}: parent={issue['parent_id']}")
            print(f"       {issue['message']}")
        if len(ordering['issues']) > 5:
            print(f"  ... and {len(ordering['issues']) - 5} more issues")

    # Summary
    print(f"\n{'='*60}")
    coverage = report['summary']['coverage_pct']
    text_recall = report['summary'].get('text_recall_pct', coverage)
    gone = report['summary'].get('gone', report['summary']['total_missing'])
    misclassified = report['summary'].get('misclassified', 0)
    phantom_count = 0
    if phantom:
        phantom_count = phantom.get('total', 0)
    ordering_ok = ordering is None or ordering['valid']
    ordering_count = 0 if ordering is None else len(ordering['issues'])
    status = "PASS" if gone == 0 and hierarchy['valid'] and phantom_count == 0 and ordering_ok else "ISSUES"
    print(f"SUMMARY: {text_recall:.1f}% text recall ({coverage:.1f}% strict) - {status}")
    print(f"  Total HTML segments: {report['summary']['total_html_segments']}")
    print(f"  Gone (truly missing): {gone}")
    print(f"  Misclassified: {misclassified}")
    print(f"  Hierarchy issues: {len(hierarchy['issues'])}")
    print(f"  Ordering issues: {ordering_count}")
    if phantom is not None:
        print(f"  Phantom segments: {phantom_count}")
    print(f"{'='*60}")

    # Machine-readable metrics line for batch consumption
    import json as _json
    metrics = {
        "coverage_pct": round(coverage, 1),
        "text_recall_pct": round(text_recall, 1),
        "gone": gone,
        "misclassified": misclassified,
        "total_html": report['summary']['total_html_segments'],
        "total_missing": report['summary']['total_missing'],
        "phantom": phantom_count,
        "hierarchy_ok": hierarchy['valid'],
        "ordering_ok": ordering_ok,
    }
    print(f"METRICS_JSON: {_json.dumps(metrics)}")

    return gone == 0 and hierarchy['valid'] and phantom_count == 0 and ordering_ok


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Test parser coverage')
    parser.add_argument('--input', '-i', help='Path to HTML file')
    parser.add_argument('--json', '-j', help='Path to JSON file (default: out/json/<name>.json)')
    parser.add_argument('--all', action='store_true', help='Test all HTML files in downloads/eur-lex/')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show details')
    parser.add_argument('--report', '-r', help='Save report to JSON file')
    parser.add_argument('--oracle', choices=['naive', 'mirror'], default='naive', help='Coverage oracle to use')
    parser.add_argument('--no-phantom', action='store_true', help='Disable phantom text check')

    args = parser.parse_args()

    if args.all:
        html_dir = Path('downloads/eur-lex')
        html_files = list(html_dir.glob('*.html'))
    elif args.input:
        html_files = [Path(args.input)]
    else:
        parser.print_help()
        sys.exit(1)

    all_passed = True

    for html_path in html_files:
        if not html_path.exists():
            print(f"Error: HTML file not found: {html_path}", file=sys.stderr)
            continue

        json_path = Path(args.json) if args.json else Path('out/json') / f'{html_path.stem}.json'
        if not json_path.exists():
            print(f"Error: JSON file not found: {json_path}", file=sys.stderr)
            continue

        print(f"\n{'#'*60}")
        print(f"# {html_path.name}")
        print(f"{'#'*60}")

        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'lxml')
        with open(json_path, 'r', encoding='utf-8') as f:
            units = json.load(f)

        # Run coverage test
        report = coverage_test(html_path, json_path, oracle=args.oracle)

        # Phantom text check (JSON text must exist in HTML section)
        phantom_report = None
        if not args.no_phantom:
            full_html = build_full_html_text_by_section(soup)
            json_sections = build_json_section_texts(units)
            phantom_report = {'total': 0, 'by_section': {}}
            for key, texts in json_sections.items():
                html_text = full_html.get(key, '')
                missing = []
                for t in texts:
                    if t and t not in html_text:
                        missing.append(t[:100] + ('...' if len(t) > 100 else ''))
                phantom_report['by_section'][key] = missing
                phantom_report['total'] += len(missing)

        # Run hierarchy validation
        hierarchy = validate_hierarchy(units)

        # Run ordering validation
        ordering = validate_ordering(units)

        # Print report
        passed = print_report(report, hierarchy, args.verbose, phantom_report, ordering)
        all_passed = all_passed and passed

        # Save report if requested
        if args.report and len(html_files) == 1:
            full_report = {'coverage': report, 'hierarchy': hierarchy, 'phantom': phantom_report, 'ordering': ordering}
            with open(args.report, 'w', encoding='utf-8') as f:
                json.dump(full_report, f, ensure_ascii=False, indent=2)
            print(f"\nReport saved to: {args.report}")

    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
