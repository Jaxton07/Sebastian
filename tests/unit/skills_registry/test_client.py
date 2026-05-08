from __future__ import annotations

import pytest

from sebastian.skills_registry import client as registry_client_module
from sebastian.skills_registry.client import (
    RegistryClient,
    RegistryUrlError,
    is_installable_status,
    resolve_registry_url,
)


def test_resolve_registry_url_prefers_argument(monkeypatch) -> None:
    monkeypatch.setenv("SEBASTIAN_SKILLS_REGISTRY_URL", "https://mirror.example")
    assert resolve_registry_url("https://custom.example") == "https://custom.example"


def test_resolve_registry_url_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("SEBASTIAN_SKILLS_REGISTRY_URL", "https://mirror.example")
    assert resolve_registry_url(None) == "https://mirror.example"


def test_resolve_registry_url_defaults(monkeypatch) -> None:
    monkeypatch.delenv("SEBASTIAN_SKILLS_REGISTRY_URL", raising=False)
    assert resolve_registry_url(None) == "https://clawhub.ai"


def test_resolve_registry_url_rejects_http() -> None:
    with pytest.raises(RegistryUrlError):
        resolve_registry_url("http://example.com")


@pytest.mark.parametrize(
    "registry_url",
    [
        "https://clawhub.ai?mirror=1",
        "https://clawhub.ai#skills",
        "https://user@clawhub.ai",
        "https://user:pass@clawhub.ai",
    ],
)
def test_resolve_registry_url_rejects_unsafe_url_parts(registry_url: str) -> None:
    with pytest.raises(RegistryUrlError):
        resolve_registry_url(registry_url)


def test_search_creates_scoped_http_client(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> list[dict[str, str]]:
            return [{"slug": "demo", "name": "Demo", "description": "A demo"}]

    class FakeClient:
        def __init__(self, *, trust_env: bool, timeout: int) -> None:
            calls.append({"trust_env": trust_env, "timeout": timeout, "closed": False})

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            calls[-1]["closed"] = True

        def get(self, url: str, *, params: dict[str, object]) -> FakeResponse:
            calls[-1]["url"] = url
            calls[-1]["params"] = params
            return FakeResponse()

    monkeypatch.setattr(registry_client_module.httpx, "Client", FakeClient)

    result = RegistryClient("https://clawhub.ai").search("demo", limit=5)

    assert result[0].slug == "demo"
    assert calls == [
        {
            "trust_env": True,
            "timeout": 30,
            "closed": True,
            "url": "https://clawhub.ai/api/v1/search",
            "params": {"q": "demo", "limit": 5},
        }
    ]


def test_inspect_creates_scoped_http_client(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, str]:
            return {"slug": "demo", "name": "Demo", "description": "A demo"}

    class FakeClient:
        def __init__(self, *, trust_env: bool, timeout: int) -> None:
            calls.append({"trust_env": trust_env, "timeout": timeout, "closed": False})

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            calls[-1]["closed"] = True

        def get(
            self,
            url: str,
            *,
            params: dict[str, object] | None,
        ) -> FakeResponse:
            calls[-1]["url"] = url
            calls[-1]["params"] = params
            return FakeResponse()

    monkeypatch.setattr(registry_client_module.httpx, "Client", FakeClient)

    result = RegistryClient("https://clawhub.ai").inspect("demo", version="1.0.0")

    assert result.slug == "demo"
    assert calls == [
        {
            "trust_env": True,
            "timeout": 30,
            "closed": True,
            "url": "https://clawhub.ai/api/v1/skills/demo",
            "params": {"version": "1.0.0"},
        }
    ]


@pytest.mark.parametrize("slug", ["../secret", "foo/bar", "foo?version=bad", "foo#bad"])
def test_inspect_rejects_unsafe_slug(slug: str) -> None:
    client = RegistryClient("https://clawhub.ai")
    with pytest.raises(RegistryUrlError):
        client.inspect(slug)


def test_direct_download_url_rejects_third_party_origin() -> None:
    client = RegistryClient("https://clawhub.ai")
    with pytest.raises(RegistryUrlError):
        client.resolve_download_url(
            {"download_url": "https://evil.example/x.zip"},
            slug="flight",
            version=None,
        )


def test_fallback_download_url_includes_slug_and_version() -> None:
    client = RegistryClient("https://clawhub.ai")

    assert client.resolve_download_url(
        {"version": "1.2.3"},
        slug="flight_search",
        version="1.2.3",
    ) == ("https://clawhub.ai/api/v1/download?slug=flight_search&version=1.2.3")


def test_parse_search_item_uses_aliases_and_stringifies_values() -> None:
    client = RegistryClient("https://clawhub.ai")

    result = client._parse_search_item(
        {
            "id": 123,
            "summary": 456,
            "version": 7,
            "status": 42,
        }
    )

    assert result.slug == "123"
    assert result.name == "123"
    assert result.description == "456"
    assert result.latest_version == "7"
    assert result.security_status == "42"


def test_parse_detail_uses_aliases_and_stringifies_values() -> None:
    client = RegistryClient("https://clawhub.ai")

    result = client._parse_detail(
        {
            "id": 123,
            "summary": 456,
            "latest_version": 7,
            "downloadUrl": "https://clawhub.ai/download.zip",
            "digest": 890,
            "status": 42,
        }
    )

    assert result.slug == "123"
    assert result.name == "123"
    assert result.description == "456"
    assert result.version == "7"
    assert result.download_url == "https://clawhub.ai/download.zip"
    assert result.sha256 == "890"
    assert result.security_status == "42"


@pytest.mark.parametrize(
    "status",
    ["malicious", "quarantined", "blocked", "hidden", "suspicious"],
)
def test_unsafe_status_is_not_installable(status: str) -> None:
    assert is_installable_status(status) is False


def test_missing_status_is_installable() -> None:
    assert is_installable_status(None) is True
