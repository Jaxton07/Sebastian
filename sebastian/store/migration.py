"""Filesystem layout migration for Sebastian data directory.

Schema versions:
- v1 (pre-2026-04): everything flat under ~/.sebastian/
- v2: split into {data, logs, run} subdirs

The marker file ``.layout-v2`` records the current schema. Migration is
idempotent: present marker → no-op.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

LAYOUT_MARKER = ".layout-v2"
CURRENT_SCHEMA = "2"

# 用户数据：从 root 搬到 data/
_USER_DATA_ENTRIES = ("sebastian.db", "secret.key", "workspace", "extensions")


def migrate_layout_v2(data_root: Path) -> None:
    """Idempotently upgrade a legacy v1 layout to v2 in-place.

    Safe to call on every startup. No-op once the marker is present.
    """
    marker = data_root / LAYOUT_MARKER
    if marker.exists():
        return

    data_root.mkdir(parents=True, exist_ok=True)

    if not _has_any_legacy_artifact(data_root):
        # Fresh install — just create the skeleton.
        _ensure_v2_dirs(data_root)
        marker.write_text(f"{CURRENT_SCHEMA}\n")
        return

    logger.info("Detected v1 layout under %s, migrating to v2...", data_root)
    _ensure_v2_dirs(data_root)

    # User data → data/
    user_data = data_root / "data"
    for name in _USER_DATA_ENTRIES:
        src = data_root / name
        if src.exists():
            shutil.move(str(src), str(user_data / name))

    # PID file → run/
    pid_src = data_root / "sebastian.pid"
    if pid_src.exists():
        shutil.move(str(pid_src), str(data_root / "run" / "sebastian.pid"))

    # Legacy update-rollback dir → run/update-backups/
    legacy_backups = data_root / "backups"
    if legacy_backups.exists():
        shutil.move(str(legacy_backups), str(data_root / "run" / "update-backups"))

    # Deprecated sessions dir
    sessions = data_root / "sessions"
    if sessions.exists():
        shutil.rmtree(sessions)

    marker.write_text(f"{CURRENT_SCHEMA}\n")
    logger.info("Layout migration v2 complete")


def _ensure_v2_dirs(data_root: Path) -> None:
    (data_root / "data").mkdir(exist_ok=True)
    (data_root / "logs").mkdir(exist_ok=True)
    (data_root / "run").mkdir(exist_ok=True)


def _has_any_legacy_artifact(data_root: Path) -> bool:
    for name in (*_USER_DATA_ENTRIES, "sebastian.pid", "backups", "sessions"):
        if (data_root / name).exists():
            return True
    return False
