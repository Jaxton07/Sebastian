from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sebastian.capabilities.skills.metadata import (
    SkillMetadataError,
    parse_skill_metadata,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillCatalogEntry:
    slug: str
    name: str
    registered_name: str
    description: str
    path: Path
    source: str


def load_skill_catalog(
    builtin_dir: Path | None = None,
    extra_dirs: list[Path] | None = None,
) -> list[SkillCatalogEntry]:
    """Scan dirs for skill subdirectories containing SKILL.md.

    Returns catalog metadata only. Skill instructions are read on demand through
    the `sebastian skills show/read` CLI, not injected as provider tool specs.
    Later dirs override earlier ones for the same Skill name.
    """
    if builtin_dir is None:
        builtin_dir = Path(__file__).parent

    dirs: list[Path] = [builtin_dir, *(extra_dirs or [])]

    skills: dict[str, SkillCatalogEntry] = {}

    for base_dir in dirs:
        if not base_dir.exists():
            continue
        for entry in sorted(base_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                metadata = parse_skill_metadata(content, fallback_name=entry.name)
            except (OSError, UnicodeDecodeError, SkillMetadataError) as exc:
                logger.warning("Skipping invalid Skill %s: %s", skill_md, exc)
                continue

            source = "builtin" if base_dir == builtin_dir else "local"
            skills[metadata.name] = SkillCatalogEntry(
                slug=entry.name,
                name=metadata.name,
                registered_name=metadata.registered_name,
                description=metadata.description,
                path=entry,
                source=source,
            )

    return list(skills.values())
