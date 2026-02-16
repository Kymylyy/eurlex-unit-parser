"""High-level library API for single-document download and parse workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eurlex_unit_parser.download.eurlex import DownloadResult, download_eurlex
from eurlex_unit_parser.models import DocumentMetadata, Unit, ValidationReport
from eurlex_unit_parser.parser.engine import EUParser


@dataclass
class ParseResult:
    """Structured parser result for one source document."""

    units: list[Unit]
    document_metadata: DocumentMetadata | None
    validation: ValidationReport
    source_file: str


@dataclass
class JobResult:
    """Outcome of a single download + parse job."""

    download: DownloadResult
    parse: ParseResult | None
    parse_error: str | None = None


def parse_html(html_content: str, source_file: str) -> ParseResult:
    """Parse HTML content and return structured results."""
    parser = EUParser(source_file=source_file)
    units = parser.parse(html_content)
    return ParseResult(
        units=list(units),
        document_metadata=parser.document_metadata,
        validation=parser.validation,
        source_file=source_file,
    )


def parse_file(input_path: str | Path) -> ParseResult:
    """Parse an HTML file from disk."""
    path = Path(input_path)
    html_content = path.read_text(encoding="utf-8")
    return parse_html(html_content, source_file=str(path))


def download_and_parse(url: str, output_path: str | Path, lang: str = "EN") -> JobResult:
    """Run download and parse for a single document target."""
    path = Path(output_path)
    download_result = download_eurlex(url, path, lang=lang)
    if not download_result.ok:
        return JobResult(download=download_result, parse=None)

    try:
        parse_result = parse_file(download_result.output_path)
    except Exception as e:
        return JobResult(download=download_result, parse=None, parse_error=str(e))
    return JobResult(download=download_result, parse=parse_result)
