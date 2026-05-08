from __future__ import annotations

import pathlib
from pathlib import Path


def test_builtin_skill_manager_is_loaded() -> None:
    from sebastian.capabilities import skills as skills_pkg
    from sebastian.capabilities.skills._loader import load_skill_catalog

    catalog = load_skill_catalog(builtin_dir=pathlib.Path(skills_pkg.__file__).parent)
    names = {entry.name for entry in catalog}
    assert "skill_manager" in names
    manager = next(entry for entry in catalog if entry.name == "skill_manager")
    assert manager.registered_name == "skill__skill_manager"
    assert "Sebastian Skills" in manager.description
    assert "sebastian skills list" not in manager.description
    assert "~/.sebastian/bin/sebastian" not in manager.description


def test_skill_loader_reads_skill_md_metadata(tmp_path: Path) -> None:
    skill_dir = tmp_path / "my_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: my_skill\ndescription: Does my thing\n---\n\nSteps: do stuff.\n"
    )

    from sebastian.capabilities.skills._loader import load_skill_catalog

    builtin_dir = tmp_path / "builtin"
    builtin_dir.mkdir()
    catalog = load_skill_catalog(builtin_dir=builtin_dir, extra_dirs=[tmp_path])

    assert len(catalog) == 1
    entry = catalog[0]
    assert entry.slug == "my_skill"
    assert entry.name == "my_skill"
    assert entry.registered_name == "skill__my_skill"
    assert entry.description == "Does my thing"
    assert entry.path == skill_dir
    assert entry.source == "local"


def test_skill_loader_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    no_skill_dir = tmp_path / "notaskill"
    no_skill_dir.mkdir()
    (no_skill_dir / "README.md").write_text("# not a skill")

    from sebastian.capabilities.skills._loader import load_skill_catalog

    builtin_dir = tmp_path / "builtin"
    builtin_dir.mkdir()
    catalog = load_skill_catalog(builtin_dir=builtin_dir, extra_dirs=[tmp_path])
    assert catalog == []


def test_skill_loader_user_dir_overrides_builtin(tmp_path: Path) -> None:
    builtin_dir = tmp_path / "builtin"
    builtin_dir.mkdir()
    user_dir = tmp_path / "user"
    user_dir.mkdir()

    for base in [builtin_dir, user_dir]:
        sd = base / "greet"
        sd.mkdir()
        src = "builtin" if base == builtin_dir else "user"
        (sd / "SKILL.md").write_text(
            f"---\nname: greet\ndescription: Greet from {src}\n---\nGreet.\n"
        )

    from sebastian.capabilities.skills._loader import load_skill_catalog

    catalog = load_skill_catalog(builtin_dir=builtin_dir, extra_dirs=[user_dir])
    greet = next(entry for entry in catalog if entry.name == "greet")
    assert greet.description == "Greet from user"
    assert greet.source == "local"
    assert greet.path == user_dir / "greet"


def test_skill_loader_skips_invalid_skill_name(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bad"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: bad name\ndescription: Bad\n---\n")

    from sebastian.capabilities.skills._loader import load_skill_catalog

    assert load_skill_catalog(builtin_dir=tmp_path) == []


def test_skill_loader_skips_binary_skill_md(tmp_path: Path) -> None:
    skill_dir = tmp_path / "binary"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_bytes(b"\xff\xfe\x00")

    from sebastian.capabilities.skills._loader import load_skill_catalog

    assert load_skill_catalog(builtin_dir=tmp_path) == []
