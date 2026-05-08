from __future__ import annotations

import pytest

from sebastian.capabilities.skills.metadata import (
    SkillMetadataError,
    parse_skill_metadata,
    validate_skill_name,
)


def test_parse_skill_metadata_reads_frontmatter() -> None:
    meta = parse_skill_metadata(
        "---\nname: flight_search\ndescription: Search flights\n---\nBody",
        fallback_name="fallback",
    )
    assert meta.name == "flight_search"
    assert meta.registered_name == "skill__flight_search"
    assert meta.description == "Search flights"
    assert meta.body == "Body"


@pytest.mark.parametrize("name", ["bad name", "../x", "skill__double", "x.y"])
def test_validate_skill_name_rejects_invalid_names(name: str) -> None:
    with pytest.raises(SkillMetadataError):
        validate_skill_name(name)
