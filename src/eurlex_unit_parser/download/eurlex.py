"""EUR-Lex HTML downloader with Playwright."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadResult:
    """Structured downloader result for orchestration and observability."""

    ok: bool
    status: str
    error: str | None
    output_path: Path
    final_url: str | None
    bytes_written: int
    method: str


def extract_name_from_url(url: str) -> str:
    """Extract a reasonable filename from EUR-Lex URL."""
    if "uri=" in url:
        uri_part = url.split("uri=")[-1].split("&")[0]
        name = uri_part.replace("OJ:", "").replace("CELEX:", "")
        name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        return name
    return "document"


def download_eurlex(url: str, output_path: Path, lang: str = "EN") -> DownloadResult:
    """Download HTML from EUR-Lex using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return DownloadResult(
            ok=False,
            status="playwright_missing",
            error="Playwright not installed.",
            output_path=output_path,
            final_url=None,
            bytes_written=0,
            method="playwright",
        )

    url = re.sub(r"/[A-Z]{2}/TXT/", f"/{lang}/TXT/", url)

    print(f"Downloading: {url}")
    print(f"Output: {output_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_selector("body", timeout=30000)

            content = page.content()

            if len(content) < 1000:
                print("Warning: Page content seems too short, might be a challenge page")
                return DownloadResult(
                    ok=False,
                    status="content_too_short",
                    error="Page content shorter than 1000 bytes.",
                    output_path=output_path,
                    final_url=url,
                    bytes_written=0,
                    method="playwright",
                )

            if "eli-container" not in content and "eli-subdivision" not in content:
                print("Warning: No ELI structure found in page")

            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except OSError as e:
                print(f"Error: {e}")
                return DownloadResult(
                    ok=False,
                    status="write_error",
                    error=str(e),
                    output_path=output_path,
                    final_url=url,
                    bytes_written=0,
                    method="playwright",
                )

            print(f"Saved {len(content):,} bytes")
            return DownloadResult(
                ok=True,
                status="ok",
                error=None,
                output_path=output_path,
                final_url=url,
                bytes_written=len(content),
                method="playwright",
            )

        except Exception as e:
            print(f"Error: {e}")
            return DownloadResult(
                ok=False,
                status="navigation_error",
                error=str(e),
                output_path=output_path,
                final_url=url,
                bytes_written=0,
                method="playwright",
            )
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download EUR-Lex HTML documents")
    parser.add_argument("url", help="EUR-Lex URL")
    parser.add_argument("name", nargs="?", help="Output filename (without .html)")
    parser.add_argument("--lang", "-l", default="EN", help="Language code (default: EN)")
    parser.add_argument("--output-dir", "-o", default="downloads/eur-lex", help="Output directory")

    args = parser.parse_args()

    name = args.name or extract_name_from_url(args.url)
    output_path = Path(args.output_dir) / f"{name}.html"

    result = download_eurlex(args.url, output_path, args.lang)
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
