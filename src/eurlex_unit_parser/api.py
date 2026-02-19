"""High-level library API for single-document download and parse workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eurlex_unit_parser.download.eurlex import DownloadResult, download_eurlex
from eurlex_unit_parser.models import DocumentMetadata, LSUSummary, Unit, ValidationReport
from eurlex_unit_parser.parser.engine import EUParser
from eurlex_unit_parser.summary import (
    LSU_STATUS_DISABLED,
    extract_celex_from_text,
    fetch_lsu_summary,
)


@dataclass
class ParseResult:
    """Structured parser result for one source document."""

    units: list[Unit]
    document_metadata: DocumentMetadata | None
    summary_lsu: LSUSummary | None
    summary_lsu_status: str
    validation: ValidationReport
    source_file: str


@dataclass
class JobResult:
    """Outcome of a single download + parse job."""

    download: DownloadResult
    parse: ParseResult | None
    parse_error: str | None = None


def parse_html(
    html_content: str,
    source_file: str,
    *,
    celex: str | None = None,
    with_summary_lsu: bool = True,
    summary_lsu_lang: str | None = None,
) -> ParseResult:
    """Parse HTML content and return structured results."""
    parser = EUParser(source_file=source_file)
    units = parser.parse(html_content)
    if with_summary_lsu:
        summary_lsu, summary_lsu_status = fetch_lsu_summary(
            html_content=html_content,
            source_file=source_file,
            celex=celex,
            language=summary_lsu_lang,
        )
    else:
        summary_lsu, summary_lsu_status = None, LSU_STATUS_DISABLED

    return ParseResult(
        units=list(units),
        document_metadata=parser.document_metadata,
        summary_lsu=summary_lsu,
        summary_lsu_status=summary_lsu_status,
        validation=parser.validation,
        source_file=source_file,
    )


def parse_file(
    input_path: str | Path,
    *,
    celex: str | None = None,
    with_summary_lsu: bool = True,
    summary_lsu_lang: str | None = None,
) -> ParseResult:
    """Parse an HTML file from disk."""
    path = Path(input_path)
    html_content = path.read_text(encoding="utf-8")
    return parse_html(
        html_content,
        source_file=str(path),
        celex=celex,
        with_summary_lsu=with_summary_lsu,
        summary_lsu_lang=summary_lsu_lang,
    )


def download_and_parse(
    url: str,
    output_path: str | Path,
    lang: str = "EN",
    *,
    with_summary_lsu: bool = True,
    summary_lsu_lang: str | None = None,
) -> JobResult:
    """Run download and parse for a single document target."""
    path = Path(output_path)
    download_result = download_eurlex(url, path, lang=lang)
    if not download_result.ok:
        return JobResult(download=download_result, parse=None)

    try:
        parse_result = parse_file(
            download_result.output_path,
            celex=extract_celex_from_text(url),
            with_summary_lsu=with_summary_lsu,
            summary_lsu_lang=summary_lsu_lang,
        )
    except Exception as e:
        return JobResult(download=download_result, parse=None, parse_error=str(e))
    return JobResult(download=download_result, parse=parse_result)
