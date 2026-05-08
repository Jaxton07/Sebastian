from __future__ import annotations

import re
from dataclasses import dataclass

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FRONTMATTER_RE = re.compile(r"^(\w+)\s*:\s*(.+)$")


class SkillMetadataError(ValueError):
    pass


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    registered_name: str
    description: str
    body: str


def validate_skill_name(name: str) -> None:
    if not name or not _NAME_RE.match(name):
        raise SkillMetadataError(f"Invalid skill name: {name!r}")
    if name.startswith("skill__"):
        raise SkillMetadataError("Skill name must not include skill__ prefix")


def parse_skill_metadata(content: str, *, fallback_name: str) -> SkillMetadata:
    meta: dict[str, str] = {}
    body = content
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            block = content[3:end].strip()
            body = content[end + 4 :].strip()
            for line in block.splitlines():
                m = _FRONTMATTER_RE.match(line.strip())
                if m:
                    meta[m.group(1)] = m.group(2).strip()
    name = meta.get("name", fallback_name)
    validate_skill_name(name)
    return SkillMetadata(
        name=name,
        registered_name=f"skill__{name}",
        description=meta.get("description", ""),
        body=body,
    )
