from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sebastian.config import Settings

logger = logging.getLogger(__name__)


class _Closable(Protocol):
    async def close(self) -> None: ...


class _Stoppable(Protocol):
    async def stop(self) -> None: ...


class _PageHandle(_Closable, Protocol):
    @property
    def url(self) -> str: ...

    async def title(self) -> str: ...


@dataclass(frozen=True)
class BrowserPageMetadata:
    url: str
    title: str | None


class BrowserSessionManager:
    def __init__(self, settings: Settings) -> None:
        self.lock = asyncio.Lock()
        self.settings = settings
        self.profile_dir: Path = settings.browser_profile_dir
        self.downloads_dir: Path = settings.browser_downloads_dir
        self.screenshots_dir: Path = settings.browser_screenshots_dir
        self.playwright: _Stoppable | None = None
        self.context: _Closable | None = None
        self.page: _PageHandle | None = None

    async def aclose(self) -> None:
        async with self.lock:
            page = self.page
            context = self.context
            playwright = self.playwright
            self.page = None
            self.context = None
            self.playwright = None

            if page is not None:
                try:
                    await page.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("browser page close failed during shutdown: %s", exc)
            if context is not None:
                try:
                    await context.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("browser context close failed during shutdown: %s", exc)
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("playwright stop failed during shutdown: %s", exc)

    async def current_page_metadata(self) -> BrowserPageMetadata | None:
        async with self.lock:
            if self.page is None:
                return None
            page = self.page

        url = str(getattr(page, "url", ""))
        title: str | None
        try:
            title = await page.title()
        except Exception as exc:  # noqa: BLE001
            logger.warning("browser page title lookup failed: %s", exc)
            title = None
        return BrowserPageMetadata(url=url, title=title)
