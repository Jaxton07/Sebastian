from __future__ import annotations

import asyncio
import inspect
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable

from sebastian.capabilities.tools.browser.safety import (
    BrowserSafetyError,
    is_forbidden_ip,
    normalize_hostname,
)

ResolverReturn = Iterable[str] | Awaitable[Iterable[str]]
ResolverFn = Callable[[str], ResolverReturn]


class BrowserDNSResolver:
    def __init__(self, resolve: ResolverFn | None = None, *, timeout_seconds: float = 5.0) -> None:
        self._resolve = resolve
        self._timeout_seconds = timeout_seconds

    async def resolve_public(self, host: str) -> list[str]:
        normalized_host = normalize_hostname(host)
        literal = _ip_literal_or_none(normalized_host)
        if literal is not None:
            if is_forbidden_ip(literal):
                raise BrowserSafetyError(
                    "Browser destination blocked: "
                    f"{normalized_host} resolves to forbidden IP {literal}"
                )
            return [literal]

        try:
            answers = await asyncio.wait_for(
                self._resolve_host(normalized_host),
                timeout=self._timeout_seconds,
            )
        except BrowserSafetyError:
            raise
        except Exception as exc:
            raise BrowserSafetyError(
                f"Browser destination blocked: DNS resolution failed for {normalized_host}"
            ) from exc

        normalized_answers = self._normalize_answers(normalized_host, answers)
        if not normalized_answers:
            raise BrowserSafetyError(
                f"Browser destination blocked: DNS returned no addresses for {normalized_host}"
            )
        return normalized_answers

    async def _resolve_host(self, host: str) -> Iterable[str]:
        if self._resolve is None:
            return await _default_resolve(host)

        result = self._resolve(host)
        if inspect.isawaitable(result):
            return await result
        return result

    def _normalize_answers(self, host: str, answers: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for answer in answers:
            try:
                ip = ipaddress.ip_address(str(answer)).compressed
            except ValueError as exc:
                raise BrowserSafetyError(
                    f"Browser destination blocked: DNS returned non-IP answer for {host}"
                ) from exc
            if is_forbidden_ip(ip):
                raise BrowserSafetyError(
                    f"Browser destination blocked: {host} resolves to forbidden IP {ip}"
                )
            if ip not in seen:
                normalized.append(ip)
                seen.add(ip)
        return normalized


async def _default_resolve(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(
        host,
        None,
        family=socket.AF_UNSPEC,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )
    answers: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip = str(sockaddr[0])
        if ip not in answers:
            answers.append(ip)
    return answers


def _ip_literal_or_none(host: str) -> str | None:
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        return None
