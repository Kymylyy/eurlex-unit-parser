#!/usr/bin/env python3
"""
EUR-Lex HTML Downloader using Playwright.

Usage:
    python download_eurlex.py <url> [output_name]

Example:
    python download_eurlex.py "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689" EMIR3
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


def extract_name_from_url(url: str) -> str:
    """Extract a reasonable filename from EUR-Lex URL."""
    # Try to extract CELEX or OJ reference
    if 'uri=' in url:
        uri_part = url.split('uri=')[-1].split('&')[0]
        # Clean up: OJ:L_202401689 -> L_202401689
        name = uri_part.replace('OJ:', '').replace('CELEX:', '')
        name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        return name
    return "document"


def download_eurlex(url: str, output_path: Path, lang: str = "EN") -> bool:
    """
    Download HTML from EUR-Lex using Playwright.

    Args:
        url: EUR-Lex URL
        output_path: Path to save HTML file
        lang: Language code (EN, PL, DE, etc.)

    Returns:
        True if successful
    """
    # Ensure language is set correctly in URL (replace any 2-letter code)
    url = re.sub(r'/[A-Z]{2}/TXT/', f'/{lang}/TXT/', url)

    print(f"Downloading: {url}")
    print(f"Output: {output_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            # Navigate and wait for content
            page.goto(url, wait_until="networkidle", timeout=60000)

            # Wait for main content to load
            page.wait_for_selector("body", timeout=30000)

            # Check if we got actual content (not a challenge page)
            content = page.content()

            if len(content) < 1000:
                print("Warning: Page content seems too short, might be a challenge page")
                return False

            # Check for ELI content markers
            if 'eli-container' not in content and 'eli-subdivision' not in content:
                print("Warning: No ELI structure found in page")
                # Still save for inspection

            # Save HTML
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"Saved {len(content):,} bytes")
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description='Download EUR-Lex HTML documents')
    parser.add_argument('url', help='EUR-Lex URL')
    parser.add_argument('name', nargs='?', help='Output filename (without .html)')
    parser.add_argument('--lang', '-l', default='EN', help='Language code (default: EN)')
    parser.add_argument('--output-dir', '-o', default='downloads/eur-lex',
                        help='Output directory')

    args = parser.parse_args()

    # Determine output filename
    name = args.name or extract_name_from_url(args.url)
    output_path = Path(args.output_dir) / f"{name}.html"

    success = download_eurlex(args.url, output_path, args.lang)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
