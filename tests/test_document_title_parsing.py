"""Tests for document title parsing from EUR-Lex OJ HTML."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from parse_eu import EUParser


HTML_DIR = Path(__file__).parent.parent / "downloads" / "eur-lex"
SAMPLE_FILES = ["DORA.html", "AI_Act.html", "AMLR.html"]


def test_document_title_is_parsed_from_main_title_block():
    html = """
    <html>
      <body>
        <div class="eli-container">
          <div class="eli-main-title" id="tit_1">
            <p class="oj-doc-ti">REGULATION (EU) 2022/2554 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL</p>
            <p class="oj-doc-ti">of 14 December 2022</p>
            <p class="oj-doc-ti">on digital operational resilience for the financial sector</p>
            <p class="oj-doc-ti">(Text with EEA relevance)</p>
          </div>
          <div class="eli-subdivision" id="rct_1">
            <p class="oj-normal">(1) This is recital text.</p>
          </div>
          <div class="eli-subdivision" id="art_1">
            <p class="oj-ti-art">Article 1</p>
            <p class="oj-normal">This Regulation lays down requirements.</p>
          </div>
        </div>
      </body>
    </html>
    """

    units = EUParser("inline.html").parse(html)

    title_units = [u for u in units if u.type == "document_title"]
    assert len(title_units) == 1
    assert units[0].type == "document_title"

    title_text = title_units[0].text
    assert "REGULATION (EU) 2022/2554" in title_text
    assert "of 14 December 2022" in title_text
    assert "on digital operational resilience for the financial sector" in title_text
    assert "Text with EEA relevance" not in title_text


@pytest.mark.parametrize("filename", SAMPLE_FILES)
def test_document_title_on_sample_downloads(filename: str):
    html_path = HTML_DIR / filename
    if not html_path.exists():
        pytest.skip(f"HTML not found: {html_path}")

    html = html_path.read_text(encoding="utf-8")
    units = EUParser(str(html_path)).parse(html)

    title_units = [u for u in units if u.type == "document_title"]
    assert len(title_units) == 1
    assert title_units[0].text
    assert "Text with EEA relevance" not in title_units[0].text
