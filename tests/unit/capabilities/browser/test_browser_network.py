from __future__ import annotations

import asyncio
import socket

import pytest

from sebastian.capabilities.tools.browser.network import BrowserDNSResolver
from sebastian.capabilities.tools.browser.proxy import FilteringProxy
from sebastian.capabilities.tools.browser.safety import BrowserSafetyError


@pytest.mark.asyncio
async def test_resolver_rejects_private_answer() -> None:
    resolver = BrowserDNSResolver(resolve=lambda host: ["10.0.0.5"])

    with pytest.raises(BrowserSafetyError):
        await resolver.resolve_public("safe-looking.example")


@pytest.mark.asyncio
async def test_resolver_rejects_ipv6_private_answer() -> None:
    resolver = BrowserDNSResolver(resolve=lambda host: ["fc00::1"])

    with pytest.raises(BrowserSafetyError):
        await resolver.resolve_public("safe-looking.example")


@pytest.mark.asyncio
async def test_resolver_rejects_cname_to_private_answer() -> None:
    resolver = BrowserDNSResolver(resolve=lambda host: ["203.0.113.10", "127.0.0.1"])

    with pytest.raises(BrowserSafetyError):
        await resolver.resolve_public("cname-to-private.example")


@pytest.mark.asyncio
async def test_resolver_blocks_empty_answer() -> None:
    resolver = BrowserDNSResolver(resolve=lambda host: [])

    with pytest.raises(BrowserSafetyError):
        await resolver.resolve_public("empty.example")


@pytest.mark.asyncio
async def test_resolver_blocks_nxdomain_and_other_errors() -> None:
    def raise_gaierror(host: str) -> list[str]:
        raise socket.gaierror(socket.EAI_NONAME, "no such host")

    resolver = BrowserDNSResolver(resolve=raise_gaierror)

    with pytest.raises(BrowserSafetyError):
        await resolver.resolve_public("missing.example")


@pytest.mark.asyncio
async def test_resolver_returns_all_public_answers() -> None:
    resolver = BrowserDNSResolver(resolve=lambda host: ["93.184.216.34", "2606:4700:4700::1111"])

    assert await resolver.resolve_public("example.com") == [
        "93.184.216.34",
        "2606:4700:4700::1111",
    ]


@pytest.mark.asyncio
async def test_resolver_supports_async_resolver() -> None:
    async def resolve(host: str) -> list[str]:
        return ["8.8.8.8"]

    resolver = BrowserDNSResolver(resolve=resolve)

    assert await resolver.resolve_public("example.com") == ["8.8.8.8"]


class _FakeWriter:
    def __init__(self) -> None:
        self.closed = False
        self.waited = False

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.waited = True


@pytest.mark.asyncio
async def test_proxy_aclose_closes_active_writers_and_cancels_handlers() -> None:
    proxy = FilteringProxy()
    writer = _FakeWriter()

    async def never_finishes() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(never_finishes())
    proxy._active_writers.add(writer)  # type: ignore[arg-type]
    proxy._active_tasks.add(task)

    await proxy.aclose()

    assert writer.closed is True
    assert writer.waited is True
    assert task.cancelled()
