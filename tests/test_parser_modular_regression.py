"""Inline regression tests for modular parser behavior."""

from __future__ import annotations

from parse_eu import EUParser


def _parse(html: str):
    return [u.__dict__ for u in EUParser("inline.html").parse(html)]


def test_oj_paragraph_and_point_structure() -> None:
    html = """
    <html><body>
      <div class="eli-container">
        <div class="eli-main-title" id="tit_1">
          <p class="oj-doc-ti">REGULATION (EU) 2024/1</p>
        </div>
        <div class="eli-subdivision" id="art_1">
          <p class="oj-ti-art">Article 1</p>
          <div id="001.001">
            <p class="oj-normal">1. Intro text.</p>
            <table><tbody><tr><td><p>(a)</p></td><td><p>Point text</p></td></tr></tbody></table>
          </div>
        </div>
      </div>
    </body></html>
    """
    units = _parse(html)

    by_id = {u["id"]: u for u in units}
    assert "art-1" in by_id
    assert "art-1.par-1" in by_id
    assert "art-1.par-1.pt-a" in by_id
    assert by_id["art-1.par-1.pt-a"]["parent_id"] == "art-1.par-1"


def test_consolidated_paragraph_and_grid_point() -> None:
    html = """
    <html><body>
      <div class="eli-subdivision" id="art_2">
        <p class="title-article-norm">Article 2</p>
        <div class="norm">
          <span class="no-parag">1.</span>
          <div class="inline-element">
            <p class="norm">Consolidated paragraph text.</p>
            <div class="grid-container">
              <div class="grid-list-column-1"><span>(a)</span></div>
              <div class="grid-list-column-2"><p class="norm">Grid point text.</p></div>
            </div>
          </div>
        </div>
      </div>
    </body></html>
    """
    units = _parse(html)
    by_id = {u["id"]: u for u in units}

    assert "art-2" in by_id
    assert "art-2.par-1" in by_id
    assert "art-2.par-1.pt-a" in by_id
    assert by_id["art-2.par-1.pt-a"]["parent_id"] == "art-2.par-1"


def test_amending_article_marks_units_as_amendment_text() -> None:
    html = """
    <html><body>
      <div class="eli-subdivision" id="art_3">
        <p class="oj-ti-art">Article 3</p>
        <p class="oj-normal">This Regulation is amended as follows:</p>
        <table>
          <tbody>
            <tr>
              <td><p>(1)</p></td>
              <td><p>Replacement text for amendment.</p></td>
            </tr>
          </tbody>
        </table>
      </div>
    </body></html>
    """
    units = _parse(html)

    point_units = [u for u in units if u["id"] == "art-3.par-1.pt-1"]
    assert len(point_units) == 1
    assert point_units[0]["is_amendment_text"] is True
    assert "Replacement text" in point_units[0]["text"]


def test_annex_part_and_item_structure() -> None:
    html = """
    <html><body>
      <div class="eli-container" id="anx_I">
        <p class="oj-doc-ti">ANNEX I</p>
        <p class="oj-ti-grseq-1">Part A</p>
        <table>
          <tbody>
            <tr>
              <td><p>(a)</p></td>
              <td><p>Annex requirement text.</p></td>
            </tr>
          </tbody>
        </table>
      </div>
    </body></html>
    """
    units = _parse(html)
    by_id = {u["id"]: u for u in units}

    assert "annex-I" in by_id
    assert "annex-I.part-A" in by_id
    assert "annex-I.part-A.item-a" in by_id
    assert by_id["annex-I.part-A.item-a"]["parent_id"] == "annex-I.part-A"


def test_oj_recital_table_preserves_dash_list_text() -> None:
    html = """
    <html><body>
      <div class="eli-subdivision" id="rct_77">
        <table>
          <tbody>
            <tr>
              <td><p>(77)</p></td>
              <td>
                <p>In order to supplement or amend certain non-essential elements:</p>
                <ul>
                  <li>— supplementing this Regulation by laying down requirements;</li>
                </ul>
                <p>It is of particular importance that the Commission carry out consultations.</p>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </body></html>
    """
    units = _parse(html)
    recital = next(u for u in units if u["id"] == "recital-77")
    text = recital["text"]
    assert "supplementing this Regulation by laying down requirements" in text
    assert "It is of particular importance that the Commission carry out consultations." in text


def test_annex_part_heading_keeps_spaces_between_inline_nodes() -> None:
    html = """
    <html><body>
      <div class="eli-container" id="anx_XVIII">
        <p class="oj-doc-ti">ANNEX XVIII</p>
        <p class="oj-ti-grseq-1"><span>Part A</span><span>Contract notice</span></p>
      </div>
    </body></html>
    """
    units = _parse(html)
    by_id = {u["id"]: u for u in units}
    assert "annex-XVIII.part-A" in by_id
    assert by_id["annex-XVIII.part-A"]["text"] == "Part A Contract notice"
