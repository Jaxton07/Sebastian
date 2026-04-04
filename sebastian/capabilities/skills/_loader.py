from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML-style frontmatter from SKILL.md content.

    Returns (metadata_dict, body_without_frontmatter).
    Only supports simple key: value lines (no nested YAML).
    """
    meta: dict[str, str] = {}
    body = content

    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_block = content[3:end].strip()
            body = content[end + 4:].strip()
            for line in fm_block.splitlines():
                m = re.match(r"^(\w+)\s*:\s*(.+)$", line.strip())
                if m:
                    meta[m.group(1)] = m.group(2).strip()

    return meta, body


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
            meta, body = _parse_frontmatter(content)

            skill_name = meta.get("name", entry.name)
            description = meta.get("description", "")
            full_instructions = f"{description}\n\n{body}".strip() if body else description

            tool_name = f"skill__{skill_name}"
            skills[skill_name] = {
                "name": tool_name,
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
