"""Tests for downloader logic with mocked Playwright runtime."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path
from types import ModuleType

import pytest

from eurlex_unit_parser.download import eurlex


class _FakePage:
    def __init__(self, content: str, raise_on_goto: bool = False):
        self._content = content
        self._raise_on_goto = raise_on_goto
        self.goto_url: str | None = None

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        _ = wait_until, timeout
        self.goto_url = url
        if self._raise_on_goto:
            raise RuntimeError("goto failed")

    def wait_for_selector(self, _selector: str, timeout: int) -> None:
        _ = timeout

    def content(self) -> str:
        return self._content


class _FakeContext:
    def __init__(self, page: _FakePage):
        self._page = page

    def new_page(self) -> _FakePage:
        return self._page


class _FakeBrowser:
    def __init__(self, page: _FakePage):
        self._page = page
        self.closed = False

    def new_context(self, user_agent: str) -> _FakeContext:
        _ = user_agent
        return _FakeContext(self._page)

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, page: _FakePage):
        self._page = page

    def launch(self, headless: bool) -> _FakeBrowser:
        _ = headless
        return _FakeBrowser(self._page)


class _FakePlaywrightCtx:
    def __init__(self, page: _FakePage):
        self.chromium = _FakeChromium(page)

    def __enter__(self) -> "_FakePlaywrightCtx":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        _ = exc_type, exc_val, exc_tb
        return False


def _install_fake_playwright(monkeypatch, page: _FakePage) -> None:
    sync_api = ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: _FakePlaywrightCtx(page)
    pkg = ModuleType("playwright")
    monkeypatch.setitem(sys.modules, "playwright", pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)


def test_extract_name_from_url_uses_uri_param() -> None:
    url = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689&from=EN"
    assert eurlex.extract_name_from_url(url) == "32024R1689"


def test_download_eurlex_returns_false_when_playwright_missing(monkeypatch, tmp_path: Path) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = eurlex.download_eurlex(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
        tmp_path / "out.html",
    )
    assert result.ok is False
    assert result.status == "playwright_missing"


def test_download_eurlex_writes_file_and_applies_language(monkeypatch, tmp_path: Path) -> None:
    content = "<html><body><div class='eli-container'>" + ("x" * 1500) + "</div></body></html>"
    page = _FakePage(content=content)
    _install_fake_playwright(monkeypatch, page)
    out_path = tmp_path / "d" / "doc.html"

    result = eurlex.download_eurlex(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
        out_path,
        lang="PL",
    )

    assert result.ok is True
    assert result.status == "ok"
    assert result.bytes_written == len(content)
    assert result.final_url is not None
    assert "/PL/TXT/" in result.final_url
    assert out_path.exists()
    assert page.goto_url is not None
    assert "/PL/TXT/" in page.goto_url


def test_download_eurlex_returns_false_for_short_content(monkeypatch, tmp_path: Path) -> None:
    page = _FakePage(content="<html><body>short</body></html>")
    _install_fake_playwright(monkeypatch, page)
    out_path = tmp_path / "short.html"

    result = eurlex.download_eurlex("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689", out_path)
    assert result.ok is False
    assert result.status == "content_too_short"
    assert not out_path.exists()


def test_download_eurlex_returns_false_on_runtime_error(monkeypatch, tmp_path: Path) -> None:
    page = _FakePage(content="<html><body>unused</body></html>", raise_on_goto=True)
    _install_fake_playwright(monkeypatch, page)

    result = eurlex.download_eurlex(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
        tmp_path / "err.html",
    )
    assert result.ok is False
    assert result.status == "navigation_error"


def test_main_returns_exit_code_based_on_download_result(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        eurlex,
        "download_eurlex",
        lambda *_args, **_kwargs: eurlex.DownloadResult(
            ok=True,
            status="ok",
            error=None,
            output_path=tmp_path / "dummy.html",
            final_url="https://eur-lex.europa.eu",
            bytes_written=1,
            method="playwright",
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["eurlex-download", "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689", "--output-dir", str(tmp_path)],
    )

    with pytest.raises(SystemExit) as exc:
        eurlex.main()
    assert exc.value.code == 0
