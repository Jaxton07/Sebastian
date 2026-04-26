from __future__ import annotations

from pathlib import Path

import pytest

from sebastian.store.migration import LAYOUT_MARKER, migrate_layout_v2


def test_fresh_install_creates_skeleton(tmp_path: Path) -> None:
    migrate_layout_v2(tmp_path)
    assert (tmp_path / LAYOUT_MARKER).read_text().strip() == "2"
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "run").is_dir()


def test_marker_present_is_noop(tmp_path: Path) -> None:
    (tmp_path / LAYOUT_MARKER).write_text("2\n")
    sentinel = tmp_path / "sebastian.db"
    sentinel.write_text("legacy")  # 应该不被搬走
    migrate_layout_v2(tmp_path)
    assert sentinel.exists()
    assert not (tmp_path / "data" / "sebastian.db").exists()


def test_v1_layout_migrated(tmp_path: Path) -> None:
    # 模拟旧布局
    (tmp_path / "sebastian.db").write_text("db")
    (tmp_path / "secret.key").write_text("secret")
    (tmp_path / "workspace").mkdir()
    (tmp_path / "workspace" / "f.txt").write_text("data")
    (tmp_path / "extensions").mkdir()
    (tmp_path / "extensions" / "skills").mkdir()
    (tmp_path / "sebastian.pid").write_text("12345")
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "old").write_text("rollback")
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "junk").write_text("legacy")

    migrate_layout_v2(tmp_path)

    # 用户数据进 data/
    assert (tmp_path / "data" / "sebastian.db").read_text() == "db"
    assert (tmp_path / "data" / "secret.key").read_text() == "secret"
    assert (tmp_path / "data" / "workspace" / "f.txt").read_text() == "data"
    assert (tmp_path / "data" / "extensions" / "skills").is_dir()

    # pid 进 run/
    assert (tmp_path / "run" / "sebastian.pid").read_text() == "12345"

    # 旧 update 回滚目录进 run/update-backups
    assert (tmp_path / "run" / "update-backups" / "old").read_text() == "rollback"

    # sessions 被删
    assert not (tmp_path / "sessions").exists()

    # 旧路径不再存在
    assert not (tmp_path / "sebastian.db").exists()
    assert not (tmp_path / "secret.key").exists()
    assert not (tmp_path / "workspace").exists()
    assert not (tmp_path / "extensions").exists()
    assert not (tmp_path / "sebastian.pid").exists()
    assert not (tmp_path / "backups").exists()

    # 标记落地
    assert (tmp_path / LAYOUT_MARKER).read_text().strip() == "2"


def test_partial_v1_layout(tmp_path: Path) -> None:
    """只有部分旧文件存在，其余项不应该报错。"""
    (tmp_path / "sebastian.db").write_text("db")
    # 没有 secret.key / workspace / extensions / pid / backups
    migrate_layout_v2(tmp_path)
    assert (tmp_path / "data" / "sebastian.db").read_text() == "db"
    assert (tmp_path / LAYOUT_MARKER).exists()


def test_migration_aborts_on_target_conflict(tmp_path: Path) -> None:
    """已存在的 data/sebastian.db 不能被静默覆盖。"""
    (tmp_path / "sebastian.db").write_text("legacy")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sebastian.db").write_text("preexisting")

    with pytest.raises(RuntimeError, match="Migration conflict"):
        migrate_layout_v2(tmp_path)

    # 标记不应落地（迁移失败）
    assert not (tmp_path / LAYOUT_MARKER).exists()
