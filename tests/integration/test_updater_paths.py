from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_backup_parent_under_run_dir(tmp_path: Path) -> None:
    from sebastian.cli import updater
    from sebastian.config import Settings

    fake_settings = Settings(sebastian_data_dir=str(tmp_path))
    with patch("sebastian.config.settings", fake_settings):
        backup = updater._backup_parent()
    assert backup == (tmp_path / "run" / "update-backups").resolve()
    assert backup.is_dir()
