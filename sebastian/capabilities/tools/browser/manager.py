from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from sebastian.capabilities.tools.browser.proxy import FilteringProxy, ProxyConfig
from sebastian.capabilities.tools.browser.safety import BrowserSafetyError, validate_public_http_url
from sebastian.config import Settings

logger = logging.getLogger(__name__)


class _Closable(Protocol):
    async def close(self) -> None: ...


class _GotoPage(_Closable, Protocol):
    @property
    def url(self) -> str: ...

    async def title(self) -> str: ...

    async def goto(self, url: str, *, timeout: int) -> object: ...


class _Stoppable(Protocol):
    async def stop(self) -> None: ...


class _BrowserContext(_Closable, Protocol):
    async def new_page(self) -> _GotoPage: ...


class _Chromium(Protocol):
    async def launch_persistent_context(self, *args: Any, **kwargs: Any) -> _BrowserContext: ...


class _Playwright(_Stoppable, Protocol):
    chromium: _Chromium


class _PlaywrightStarter(Protocol):
    async def start(self) -> _Playwright: ...


class _PlaywrightFactory(Protocol):
    def __call__(self) -> _PlaywrightStarter: ...


class _FilteringProxyHandle(Protocol):
    async def start(self) -> ProxyConfig: ...

    async def aclose(self) -> None: ...

    def playwright_proxy_config(self) -> dict[str, str]: ...


@dataclass(frozen=True)
class BrowserPageMetadata:
    url: str
    title: str | None


@dataclass(frozen=True)
class BrowserOpenResult:
    ok: bool
    url: str | None = None
    error: str = ""


class BrowserSessionManager:
    def __init__(
        self,
        settings: Settings,
        *,
        playwright_factory: _PlaywrightFactory | None = None,
        filtering_proxy: _FilteringProxyHandle | None = None,
    ) -> None:
        self.lock = asyncio.Lock()
        self.settings = settings
        self.profile_dir: Path = settings.browser_profile_dir
        self.downloads_dir: Path = settings.browser_downloads_dir
        self.screenshots_dir: Path = settings.browser_screenshots_dir
        self._playwright_factory = playwright_factory or _default_playwright_factory
        self._filtering_proxy = filtering_proxy or FilteringProxy()
        self._startup_lock = asyncio.Lock()
        self._navigation_lock = asyncio.Lock()
        self._playwright: _Playwright | None = None
        self._context: _BrowserContext | None = None
        self._page: _GotoPage | None = None
        self._proxy_started = False
        self._current_page_owned_by_browser_tool = False

    async def open(self, url: str) -> BrowserOpenResult:
        try:
            requested = validate_public_http_url(url)
        except BrowserSafetyError as exc:
            return BrowserOpenResult(ok=False, error=str(exc))

        async with self._navigation_lock:
            page: _GotoPage | None = None
            try:
                page = await self.page()
                await page.goto(requested.url, timeout=self.settings.sebastian_browser_timeout_ms)
                final = validate_public_http_url(str(page.url))
            except BrowserSafetyError as exc:
                async with self.lock:
                    if page is not None and self._page is page:
                        self._page = None
                    self._current_page_owned_by_browser_tool = False
                if page is not None:
                    await self._close_page_after_block(page)
                return BrowserOpenResult(ok=False, error=str(exc))
            except Exception as exc:  # noqa: BLE001
                message = _playwright_error_message(exc)
                if message is None:
                    message = f"Browser open failed: {exc}"
                return BrowserOpenResult(ok=False, error=message)

            async with self.lock:
                self._page = page
                self._current_page_owned_by_browser_tool = True
            return BrowserOpenResult(ok=True, url=final.url)

    async def page(self) -> _GotoPage:
        async with self._startup_lock:
            async with self.lock:
                if self._page is not None:
                    return self._page

            context = await self._ensure_context()
            page = await context.new_page()

            async with self.lock:
                if self._page is None:
                    self._page = page
                    return page
                await page.close()
                return self._page

    async def aclose(self) -> None:
        async with self.lock:
            page = self._page
            context = self._context
            playwright = self._playwright
            proxy = self._filtering_proxy if self._proxy_started else None
            self._page = None
            self._context = None
            self._playwright = None
            self._proxy_started = False
            self._current_page_owned_by_browser_tool = False

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
            if proxy is not None:
                try:
                    await proxy.aclose()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("browser proxy close failed during shutdown: %s", exc)
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("playwright stop failed during shutdown: %s", exc)

    async def current_page_metadata(self) -> BrowserPageMetadata | None:
        async with self.lock:
            if self._page is None:
                return None
            page = self._page

        url = str(getattr(page, "url", ""))
        title: str | None
        try:
            title = await page.title()
        except Exception as exc:  # noqa: BLE001
            logger.warning("browser page title lookup failed: %s", exc)
            title = None
        return BrowserPageMetadata(url=url, title=title)

    def parse_viewport(self) -> dict[str, int]:
        raw = self.settings.sebastian_browser_viewport.strip().lower()
        try:
            width_text, height_text = raw.split("x", maxsplit=1)
            width = int(width_text)
            height = int(height_text)
        except ValueError as exc:
            raise ValueError(
                f"Invalid browser viewport {self.settings.sebastian_browser_viewport!r}; "
                "expected WIDTHxHEIGHT"
            ) from exc
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Invalid browser viewport {self.settings.sebastian_browser_viewport!r}; "
                "width and height must be positive"
            )
        return {"width": width, "height": height}

    async def _ensure_context(self) -> _BrowserContext:
        async with self.lock:
            if self._context is not None:
                return self._context

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        proxy_config = await self._start_proxy_fail_closed()
        try:
            playwright = await self._playwright_factory().start()
            async with self.lock:
                self._playwright = playwright
            context = await playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=self.settings.sebastian_browser_headless,
                viewport=self.parse_viewport(),
                accept_downloads=True,
                downloads_path=str(self.downloads_dir),
                timeout=self.settings.sebastian_browser_timeout_ms,
                proxy=proxy_config,
            )
        except Exception:
            await self.aclose()
            raise

        async with self.lock:
            self._context = context
            return context

    async def _close_page_after_block(self, page: _GotoPage) -> None:
        try:
            await page.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("browser page close failed after blocked navigation: %s", exc)

    async def _start_proxy_fail_closed(self) -> dict[str, str]:
        try:
            await self._filtering_proxy.start()
            proxy_config = self._filtering_proxy.playwright_proxy_config()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Browser proxy failed to start; refusing direct network fallback: "
                f"{exc}"
            ) from exc

        server = proxy_config.get("server", "")
        if not server:
            raise RuntimeError(
                "Browser proxy config is unavailable; refusing direct network fallback"
            )
        proxy_config = {**proxy_config, "bypass": ""}
        async with self.lock:
            self._proxy_started = True
        return proxy_config


def _default_playwright_factory() -> _PlaywrightStarter:
    try:
        from playwright.async_api import async_playwright  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Ask the user to run: "
            "python -m playwright install chromium"
        ) from exc
    return cast(_PlaywrightStarter, async_playwright())


def _playwright_error_message(exc: Exception) -> str | None:
    text = str(exc)
    lowered = text.lower()
    if "executable doesn't exist" in lowered or "browserType.launch" in text:
        return (
            "Browser executable is missing. Ask the user to run: "
            "python -m playwright install chromium"
        )
    if (
        "host system is missing dependencies" in lowered
        or "missing dependencies" in lowered
        or "install-deps" in lowered
    ):
        return (
            "Browser system dependencies are missing. Ask the user to run: "
            "python -m playwright install-deps chromium"
        )
    return None
