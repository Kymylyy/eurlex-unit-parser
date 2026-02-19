"""Fetch and parse EUR-Lex LSU (Summaries of EU legislation) pages."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup, Tag

from eurlex_unit_parser.models import LSUSummary, LSUSummarySection

LSU_STATUS_OK = "ok"
LSU_STATUS_NOT_FOUND = "not_found"
LSU_STATUS_FETCH_ERROR = "fetch_error"
LSU_STATUS_CELEX_MISSING = "celex_missing"
LSU_STATUS_DISABLED = "disabled"

_STATUS_VALUES = {
    LSU_STATUS_OK,
    LSU_STATUS_NOT_FOUND,
    LSU_STATUS_FETCH_ERROR,
    LSU_STATUS_CELEX_MISSING,
    LSU_STATUS_DISABLED,
}

_BASE_CELEX_RE = re.compile(r"\b([0-9][0-9]{4}[A-Z][0-9]{4})\b")
_CONSOLIDATED_CELEX_RE = re.compile(r"\b(0[0-9]{4}[A-Z][0-9]{4}-[0-9]{8})\b")
_ANY_CELEX_RE = re.compile(
    r"(?:CELEX:)?(0[0-9]{4}[A-Z][0-9]{4}-[0-9]{8}|[0-9][0-9]{4}[A-Z][0-9]{4})",
    flags=re.IGNORECASE,
)
_MISSING_SUMMARY_RE = re.compile(r"requested document does not exist", flags=re.IGNORECASE)
_HTML_LANG_RE = re.compile(r'<html[^>]+\blang=["\']([a-zA-Z-]{2,10})["\']', flags=re.IGNORECASE)
_URL_LANG_RE = re.compile(r"/legal-content/([A-Za-z]{2})/")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_language(language: str | None) -> str:
    if not language:
        return "EN"
    return language.strip().split("-")[0].upper() or "EN"


def extract_celex_from_text(text: str) -> str | None:
    """Extract CELEX (base or consolidated) from arbitrary text."""
    match = _ANY_CELEX_RE.search(unquote(text or ""))
    if not match:
        return None
    return match.group(1).upper()


def _base_celex_from_consolidated(celex: str) -> str | None:
    match = _CONSOLIDATED_CELEX_RE.fullmatch(celex)
    if not match:
        return None
    return f"3{celex[1:10]}"


def detect_language_from_html(html_content: str | None) -> str | None:
    """Best-effort source language detection from EUR-Lex source HTML."""
    if not html_content:
        return None

    wt_match = re.search(
        r'<meta[^>]+name=["\']WT\.z_usr_lan["\'][^>]+content=["\']([^"\']+)["\']',
        html_content,
        flags=re.IGNORECASE,
    )
    if wt_match:
        return _normalize_language(wt_match.group(1))

    html_match = _HTML_LANG_RE.search(html_content)
    if html_match:
        return _normalize_language(html_match.group(1))

    url_match = _URL_LANG_RE.search(html_content)
    if url_match:
        return _normalize_language(url_match.group(1))

    return None


def _extract_celex_candidates(
    *,
    explicit_celex: str | None,
    html_content: str | None,
    source_file: str | None,
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def add_candidate(raw_value: str | None) -> None:
        if not raw_value:
            return
        candidate = extract_celex_from_text(raw_value)
        if not candidate:
            return
        for token in (candidate, _base_celex_from_consolidated(candidate)):
            if not token or token in seen:
                continue
            seen.add(token)
            ordered.append(token)

    add_candidate(explicit_celex)

    if html_content:
        soup = BeautifulSoup(html_content, "lxml")
        for meta_name in ("WT.z_docID", "DC.identifier"):
            meta = soup.find("meta", attrs={"name": meta_name})
            if meta and meta.get("content"):
                add_candidate(str(meta["content"]))
        add_candidate(html_content)

    if source_file:
        stem = Path(source_file).stem
        add_candidate(stem)

    return ordered


def _extract_section_content(section: Tag) -> str:
    lines: list[str] = []
    heading = section.find("h2")

    for child in section.children:
        if heading is not None and child is heading:
            continue
        if not isinstance(child, Tag):
            text = _normalize_text(str(child))
            if text:
                lines.append(text)
            continue

        name = child.name
        if name in {"script", "style"}:
            continue
        if name in {"ul", "ol"}:
            for li in child.find_all("li"):
                item_text = _normalize_text(li.get_text(" ", strip=True))
                if item_text:
                    lines.append(f"- {item_text}")
            continue

        text = _normalize_text(child.get_text(" ", strip=True))
        if text:
            lines.append(text)

    return "\n".join(lines).strip()


def _is_missing_summary_page(soup: BeautifulSoup) -> bool:
    for alert in soup.select("div.alert.alert-warning"):
        if _MISSING_SUMMARY_RE.search(alert.get_text(" ", strip=True)):
            return True
    return False


def _parse_lsu_html(
    html_text: str,
    *,
    celex: str,
    language: str,
    source_url: str,
    final_url: str | None,
) -> tuple[LSUSummary | None, str]:
    soup = BeautifulSoup(html_text or "", "lxml")

    if _is_missing_summary_page(soup):
        return None, LSU_STATUS_NOT_FOUND

    title_tag = soup.find("h1")
    title = _normalize_text(title_tag.get_text(" ", strip=True)) if title_tag else ""

    sections: list[LSUSummarySection] = []
    for section_node in soup.select("section[id^='lseu-section-']"):
        heading_tag = section_node.find("h2")
        heading = _normalize_text(heading_tag.get_text(" ", strip=True)) if heading_tag else ""
        content = _extract_section_content(section_node)
        if heading or content:
            sections.append(LSUSummarySection(heading=heading, content=content))

    if not title and not sections:
        return None, LSU_STATUS_NOT_FOUND

    canonical_url: str | None = None
    canonical = soup.select_one("link[rel='canonical']")
    if canonical and canonical.get("href"):
        canonical_url = urljoin(final_url or source_url, str(canonical["href"]))

    last_modified_text: str | None = None
    last_modified_date: str | None = None
    lastmod = soup.select_one("p.lseu-lastmod")
    if lastmod:
        last_modified_text = _normalize_text(lastmod.get_text(" ", strip=True))
        time_tag = lastmod.find("time")
        if time_tag and time_tag.get("datetime"):
            last_modified_date = str(time_tag["datetime"]).strip()

    return (
        LSUSummary(
            celex=celex,
            language=language,
            title=title,
            sections=sections,
            source_url=source_url,
            canonical_url=canonical_url,
            last_modified_text=last_modified_text,
            last_modified_date=last_modified_date,
        ),
        LSU_STATUS_OK,
    )


def fetch_lsu_summary(
    *,
    html_content: str | None = None,
    source_file: str | None = None,
    celex: str | None = None,
    language: str | None = None,
    timeout: float = 20.0,
) -> tuple[LSUSummary | None, str]:
    """Fetch and parse LSU summary for CELEX resolved from explicit and source hints."""
    resolved_language = _normalize_language(language or detect_language_from_html(html_content))
    candidates = _extract_celex_candidates(
        explicit_celex=celex,
        html_content=html_content,
        source_file=source_file,
    )

    if not candidates:
        return None, LSU_STATUS_CELEX_MISSING

    had_not_found = False
    had_fetch_error = False

    for candidate in candidates:
        request_url = (
            f"https://eur-lex.europa.eu/legal-content/{resolved_language}/LSU/?uri=CELEX:{candidate}"
        )
        try:
            response = requests.get(
                request_url,
                timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": "eurlex-unit-parser/0.1"},
            )
        except requests.RequestException:
            had_fetch_error = True
            continue

        summary, status = _parse_lsu_html(
            response.text,
            celex=candidate,
            language=resolved_language,
            source_url=request_url,
            final_url=response.url,
        )
        if status == LSU_STATUS_OK and summary is not None:
            return summary, LSU_STATUS_OK
        if status == LSU_STATUS_NOT_FOUND:
            had_not_found = True
            continue

        had_fetch_error = True

    if had_not_found:
        return None, LSU_STATUS_NOT_FOUND
    if had_fetch_error:
        return None, LSU_STATUS_FETCH_ERROR
    return None, LSU_STATUS_NOT_FOUND


def is_lsu_status(value: str) -> bool:
    """Return True if status belongs to LSU contract enum values."""
    return value in _STATUS_VALUES
