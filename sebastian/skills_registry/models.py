from __future__ import annotations

from dataclasses import dataclass


class SkillRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SkillSearchResult:
    slug: str
    name: str
    description: str
    latest_version: str | None = None
    security_status: str | None = None


@dataclass(frozen=True)
class SkillDetail:
    slug: str
    name: str
    description: str
    version: str | None
    download_url: str | None
    sha256: str | None
    security_status: str | None
    raw: dict[str, object]
