from __future__ import annotations

from pathlib import Path

import pytest

from sebastian.config import Settings


class _CloseRecorder:
    def __init__(self, name: str, calls: list[str], *, fail: bool = False) -> None:
        self.name = name
        self.calls = calls
        self.fail = fail
        self.url = ""

    async def close(self) -> None:
        self.calls.append(self.name)
        if self.fail:
            raise RuntimeError(f"{self.name} close failed")

    async def title(self) -> str:
        return ""


class _StopRecorder:
    def __init__(self, name: str, calls: list[str], *, fail: bool = False) -> None:
        self.name = name
        self.calls = calls
        self.fail = fail

    async def stop(self) -> None:
        self.calls.append(self.name)
        if self.fail:
            raise RuntimeError(f"{self.name} stop failed")


def _settings(tmp_path: Path) -> Settings:
    return Settings(sebastian_data_dir=str(tmp_path))


@pytest.mark.asyncio
async def test_aclose_closes_page_context_and_playwright_in_order(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.browser.manager import BrowserSessionManager

    calls: list[str] = []
    manager = BrowserSessionManager(_settings(tmp_path))
    manager.page = _CloseRecorder("page", calls)
    manager.context = _CloseRecorder("context", calls)
    manager.playwright = _StopRecorder("playwright", calls)

    await manager.aclose()

    assert calls == ["page", "context", "playwright"]
    assert manager.page is None
    assert manager.context is None
    assert manager.playwright is None


@pytest.mark.asyncio
async def test_aclose_is_idempotent_and_continues_after_close_errors(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.browser.manager import BrowserSessionManager

    calls: list[str] = []
    manager = BrowserSessionManager(_settings(tmp_path))
    manager.page = _CloseRecorder("page", calls, fail=True)
    manager.context = _CloseRecorder("context", calls, fail=True)
    manager.playwright = _StopRecorder("playwright", calls, fail=True)

    await manager.aclose()
    await manager.aclose()

    assert calls == ["page", "context", "playwright"]
    assert manager.page is None
    assert manager.context is None
    assert manager.playwright is None


@pytest.mark.asyncio
async def test_current_page_metadata_returns_none_without_page(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.browser.manager import BrowserSessionManager

    manager = BrowserSessionManager(_settings(tmp_path))

    assert await manager.current_page_metadata() is None


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://example.test/path"

    async def close(self) -> None:
        return None

    async def title(self) -> str:
        return "Example Page"


class _BrokenTitlePage:
    def __init__(self) -> None:
        self.url = "https://example.test/broken"

    async def close(self) -> None:
        return None

    async def title(self) -> str:
        raise RuntimeError("title unavailable")


@pytest.mark.asyncio
async def test_current_page_metadata_reads_url_and_title(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.browser.manager import BrowserSessionManager

    manager = BrowserSessionManager(_settings(tmp_path))
    manager.page = _FakePage()

    metadata = await manager.current_page_metadata()

    assert metadata is not None
    assert metadata.url == "https://example.test/path"
    assert metadata.title == "Example Page"


@pytest.mark.asyncio
async def test_current_page_metadata_tolerates_title_errors(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.browser.manager import BrowserSessionManager

    manager = BrowserSessionManager(_settings(tmp_path))
    manager.page = _BrokenTitlePage()

    metadata = await manager.current_page_metadata()

    assert metadata is not None
    assert metadata.url == "https://example.test/broken"
    assert metadata.title is None
