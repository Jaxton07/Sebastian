from __future__ import annotations

import os
import re
from urllib.parse import urljoin, urlparse

import httpx

from sebastian.skills_registry.models import (
    SkillDetail,
    SkillRegistryError,
    SkillSearchResult,
)

DEFAULT_REGISTRY_URL = "https://clawhub.ai"
HTTP_TIMEOUT_SECONDS = 30
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
UNSAFE_STATUSES = {"malicious", "quarantined", "blocked", "hidden", "suspicious"}


class RegistryUrlError(SkillRegistryError):
    pass


def resolve_registry_url(registry: str | None) -> str:
    raw_url = registry or os.environ.get("SEBASTIAN_SKILLS_REGISTRY_URL") or DEFAULT_REGISTRY_URL
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RegistryUrlError("Skill registry URL must be an https URL")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RegistryUrlError(
            "Skill registry URL must not include query, fragment, or credentials"
        )
    return raw_url.rstrip("/")


def is_installable_status(status: str | None) -> bool:
    return status is None or status.lower() not in UNSAFE_STATUSES


class RegistryClient:
    def __init__(self, registry_url: str | None = None) -> None:
        self.registry_url = resolve_registry_url(registry_url)

    def search(self, query: str, *, limit: int = 20) -> list[SkillSearchResult]:
        with httpx.Client(trust_env=True, timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = client.get(
                f"{self.registry_url}/api/v1/search",
                params={"q": query, "limit": limit},
            )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("items", [])
        else:
            items = []
        return [self._parse_search_item(item) for item in items if isinstance(item, dict)]

    def inspect(self, slug: str, *, version: str | None = None) -> SkillDetail:
        self._validate_slug(slug)
        params = {"version": version} if version is not None else None
        with httpx.Client(trust_env=True, timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = client.get(
                f"{self.registry_url}/api/v1/skills/{slug}",
                params=params,
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise SkillRegistryError("Skill detail response must be an object")
        return self._parse_detail(payload)

    def resolve_download_url(self, data: dict[str, object]) -> str:
        for key in ("download_url", "downloadUrl", "url"):
            value = self._maybe_str(data.get(key))
            if value is not None:
                return self._validate_direct_download_url(value)
        return urljoin(self.registry_url + "/", "api/v1/download")

    def _validate_slug(self, slug: str) -> None:
        if not SLUG_PATTERN.fullmatch(slug):
            raise RegistryUrlError("Skill slug must contain only letters, numbers, '_' or '-'")

    def _validate_direct_download_url(self, download_url: str) -> str:
        parsed = urlparse(download_url)
        registry = urlparse(self.registry_url)
        if parsed.scheme != "https" or parsed.netloc != registry.netloc:
            raise RegistryUrlError("Download URL must use https and match registry origin")
        return download_url

    def _parse_search_item(self, item: dict[object, object]) -> SkillSearchResult:
        slug = self._maybe_str(item.get("slug"))
        if slug is None:
            slug = self._maybe_str(item.get("id")) or ""
        name = self._maybe_str(item.get("name")) or slug
        description = self._maybe_str(item.get("description"))
        if description is None:
            description = self._maybe_str(item.get("summary")) or ""
        latest_version = self._maybe_str(item.get("latest_version"))
        if latest_version is None:
            latest_version = self._maybe_str(item.get("version"))
        security_status = self._maybe_str(item.get("security_status"))
        if security_status is None:
            security_status = self._maybe_str(item.get("status"))
        return SkillSearchResult(
            slug=slug,
            name=name,
            description=description,
            latest_version=latest_version,
            security_status=security_status,
        )

    def _parse_detail(self, data: dict[object, object]) -> SkillDetail:
        slug = self._maybe_str(data.get("slug"))
        if slug is None:
            slug = self._maybe_str(data.get("id")) or ""
        name = self._maybe_str(data.get("name")) or slug
        description = self._maybe_str(data.get("description"))
        if description is None:
            description = self._maybe_str(data.get("summary")) or ""
        version = self._maybe_str(data.get("version"))
        if version is None:
            version = self._maybe_str(data.get("latest_version"))
        download_url = self._maybe_str(data.get("download_url"))
        if download_url is None:
            download_url = self._maybe_str(data.get("downloadUrl"))
        sha256 = self._maybe_str(data.get("sha256"))
        if sha256 is None:
            sha256 = self._maybe_str(data.get("digest"))
        security_status = self._maybe_str(data.get("security_status"))
        if security_status is None:
            security_status = self._maybe_str(data.get("status"))
        return SkillDetail(
            slug=slug,
            name=name,
            description=description,
            version=version,
            download_url=download_url,
            sha256=sha256,
            security_status=security_status,
            raw=dict(data),
        )

    @staticmethod
    def _maybe_str(value: object) -> str | None:
        return None if value is None else str(value)
