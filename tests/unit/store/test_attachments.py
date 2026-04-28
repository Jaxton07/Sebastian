from __future__ import annotations

from pathlib import Path

from sebastian.config import Settings


def test_attachments_dir_lives_under_user_data_dir(tmp_path: Path) -> None:
    settings = Settings(sebastian_data_dir=str(tmp_path))
    assert settings.attachments_dir == tmp_path / "data" / "attachments"
