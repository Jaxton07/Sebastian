from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sebastian.capabilities.skills.metadata import (
    SkillMetadataError,
    parse_skill_metadata,
)

logger = logging.getLogger(__name__)


def load_skills(
    builtin_dir: Path | None = None,
    extra_dirs: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Scan dirs for skill subdirectories containing SKILL.md.

    Returns a list of tool spec dicts suitable for CapabilityRegistry.
    Tool names are prefixed with "skill__".
    Later dirs override earlier ones for the same skill name.
    """
    if builtin_dir is None:
        builtin_dir = Path(__file__).parent

    dirs: list[Path] = [builtin_dir, *(extra_dirs or [])]

    skills: dict[str, dict[str, Any]] = {}

    for base_dir in dirs:
        if not base_dir.exists():
            continue
        for entry in sorted(base_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue

            content = skill_md.read_text(encoding="utf-8")
            try:
                metadata = parse_skill_metadata(content, fallback_name=entry.name)
            except SkillMetadataError as exc:
                logger.warning("Skipping invalid Skill %s: %s", skill_md, exc)
                continue

            full_instructions = (
                f"{metadata.description}\n\n{metadata.body}".strip()
                if metadata.body
                else metadata.description
            )

            skills[metadata.name] = {
                "name": metadata.registered_name,
                "description": full_instructions,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "instructions": {
                            "type": "string",
                            "description": (
                                "Additional context or specific instructions"
                                " for this skill invocation."
                            ),
                        }
                    },
                    "required": [],
                },
            }

    return list(skills.values())
