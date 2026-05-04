from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sebastian.cli.service_templates import (
    render_launchd_plist,
    render_systemd_unit,
)


def test_systemd_unit_contains_exec_start(tmp_path: Path) -> None:
    install_bin = tmp_path / ".venv" / "bin" / "sebastian"
    logs_dir = tmp_path / "logs"
    env_file = tmp_path / ".env"
    unit = render_systemd_unit(
        install_bin=install_bin,
        logs_dir=logs_dir,
        env_file=env_file,
    )
    assert f"ExecStart={install_bin} serve" in unit
    assert f"EnvironmentFile=-{env_file}" in unit
    assert "Restart=on-failure" in unit
    assert f"StandardOutput=append:{logs_dir / 'service.out.log'}" in unit
    assert f"StandardError=append:{logs_dir / 'service.err.log'}" in unit
    assert "WantedBy=default.target" in unit


def test_launchd_plist_renders_paths(tmp_path: Path) -> None:
    install_bin = Path("/Users/eric/.sebastian/app/.venv/bin/sebastian")
    logs_dir = Path("/Users/eric/.sebastian/logs")
    env_file = Path("/Users/eric/.sebastian/.env")
    plist = render_launchd_plist(
        install_bin=install_bin,
        logs_dir=logs_dir,
        env_file=env_file,
    )
    assert "<key>Label</key><string>com.sebastian</string>" in plist
    assert f"<string>{install_bin}</string>" in plist
    assert "<key>EnvironmentVariables</key>" in plist
    assert "<key>SEBASTIAN_ENV_FILE</key>" in plist
    assert f"<string>{env_file}</string>" in plist
    assert "<key>WorkingDirectory</key>" in plist
    assert f"<string>{logs_dir / 'service.out.log'}</string>" in plist
    assert "<key>RunAtLoad</key><true/>" in plist
    assert "<key>KeepAlive</key>" in plist
    assert "<key>SuccessfulExit</key><false/>" in plist


@pytest.fixture
def linux_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sebastian.cli.service.sys.platform", "linux")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    return fake_home


@pytest.fixture
def macos_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sebastian.cli.service.sys.platform", "darwin")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    return fake_home


def _fake_install_dir(tmp_path: Path) -> Path:
    """Return a fake install dir that satisfies resolve_install_dir validation."""
    d = tmp_path / "app"
    (d / ".venv" / "bin").mkdir(parents=True)
    (d / ".venv" / "bin" / "sebastian").touch()
    return d


def test_install_writes_systemd_unit_on_linux(linux_env: Path, tmp_path: Path) -> None:
    from sebastian.cli import service

    fake_dir = _fake_install_dir(tmp_path)
    data_dir = tmp_path / "data-root"
    with (
        patch.object(service.subprocess, "run", return_value=MagicMock(returncode=0)) as run,
        patch("sebastian.cli.updater.resolve_install_dir", return_value=fake_dir),
        patch("sebastian.config.settings.sebastian_data_dir", str(data_dir)),
    ):
        service.install()

    unit = linux_env / ".config/systemd/user/sebastian.service"
    assert unit.is_file()
    content = unit.read_text()
    env_file = data_dir / ".env"
    assert "Sebastian personal AI butler" in content
    assert str(fake_dir / ".venv" / "bin" / "sebastian") in content
    assert f"EnvironmentFile=-{env_file}" in content
    assert env_file.is_file()
    assert f"SEBASTIAN_DATA_DIR={data_dir}" in env_file.read_text()
    cmds = [call.args[0] for call in run.call_args_list]
    assert ["systemctl", "--user", "daemon-reload"] in cmds
    assert ["systemctl", "--user", "enable", "--now", "sebastian.service"] in cmds


def test_install_writes_plist_on_macos(macos_env: Path, tmp_path: Path) -> None:
    from sebastian.cli import service

    fake_dir = _fake_install_dir(tmp_path)
    data_dir = tmp_path / "data-root"
    with (
        patch.object(service.subprocess, "run", return_value=MagicMock(returncode=0)) as run,
        patch("sebastian.cli.updater.resolve_install_dir", return_value=fake_dir),
        patch("sebastian.config.settings.sebastian_data_dir", str(data_dir)),
    ):
        service.install()

    plist = macos_env / "Library/LaunchAgents/com.sebastian.plist"
    assert plist.is_file()
    content = plist.read_text()
    env_file = data_dir / ".env"
    assert "com.sebastian" in content
    assert str(fake_dir / ".venv" / "bin" / "sebastian") in content
    assert "<key>SEBASTIAN_ENV_FILE</key>" in content
    assert f"<string>{env_file}</string>" in content
    assert env_file.is_file()
    assert f"SEBASTIAN_DATA_DIR={data_dir}" in env_file.read_text()
    cmds = [call.args[0] for call in run.call_args_list]
    assert ["launchctl", "load", "-w", str(plist)] in cmds


def test_install_preserves_existing_service_env_file(linux_env: Path, tmp_path: Path) -> None:
    from sebastian.cli import service

    fake_dir = _fake_install_dir(tmp_path)
    data_dir = tmp_path / "data-root"
    env_file = data_dir / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("SEBASTIAN_BROWSER_UPSTREAM_PROXY=http://127.0.0.1:1082\n")
    original = env_file.read_text()

    with (
        patch.object(service.subprocess, "run", return_value=MagicMock(returncode=0)),
        patch("sebastian.cli.updater.resolve_install_dir", return_value=fake_dir),
        patch("sebastian.config.settings.sebastian_data_dir", str(data_dir)),
    ):
        service.install()

    unit = linux_env / ".config/systemd/user/sebastian.service"
    assert unit.is_file()
    assert f"EnvironmentFile=-{env_file}" in unit.read_text()
    assert env_file.read_text() == original


def test_install_refuses_when_unit_exists(linux_env: Path) -> None:
    from sebastian.cli import service

    unit = linux_env / ".config/systemd/user/sebastian.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[stale]")

    with pytest.raises(service.ServiceError, match="已存在"):
        service.install()


def test_systemd_service_state_reports_installed_and_active(
    linux_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    unit = linux_env / ".config/systemd/user/sebastian.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[Unit]\nDescription=Sebastian\n")

    def fake_run(cmd, capture_output=False, text=False, check=False):
        assert cmd == ["systemctl", "--user", "is-active", "sebastian.service"]
        return MagicMock(returncode=0, stdout="active\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    state = service.get_service_state()

    assert state.kind == "systemd"
    assert state.installed is True
    assert state.active is True
    assert "systemd user service: active" in state.status_text
    assert "systemctl --user status sebastian" in state.status_text
    assert "sebastian service restart" in state.status_text


def test_systemd_status_output_suggests_correct_commands(
    linux_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    unit = linux_env / ".config/systemd/user/sebastian.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[Unit]\n")
    monkeypatch.setattr(
        service.subprocess,
        "run",
        lambda *args, **kwargs: MagicMock(returncode=0, stdout="active\n", stderr=""),
    )

    output = service.status()

    assert "systemd user service: active" in output
    assert "systemctl --user status sebastian" in output
    assert "sebastian service restart" in output


def test_launchd_service_state_reports_loaded(
    macos_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    plist = macos_env / "Library/LaunchAgents/com.sebastian.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text("<plist/>")

    def fake_run(cmd, capture_output=False, text=False, check=False):
        assert cmd == ["launchctl", "list", "com.sebastian"]
        return MagicMock(returncode=0, stdout="123\t0\tcom.sebastian\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    state = service.get_service_state()

    assert state.kind == "launchd"
    assert state.installed is True
    assert state.active is True
    assert state.status_text.startswith("launchd:")


def test_launchd_service_state_reports_loaded_but_not_running(
    macos_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    plist = macos_env / "Library/LaunchAgents/com.sebastian.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text("<plist/>")

    def fake_run(cmd, capture_output=False, text=False, check=False):
        assert cmd == ["launchctl", "list", "com.sebastian"]
        return MagicMock(returncode=0, stdout="-\t0\tcom.sebastian\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    state = service.get_service_state()

    assert state.kind == "launchd"
    assert state.installed is True
    assert state.active is False
    assert "launchd: loaded but not running" in state.status_text
    assert "launchctl list com.sebastian" in state.status_text
    assert "sebastian service restart" in state.status_text


def test_restart_systemd_service_uses_systemctl(
    linux_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    unit = linux_env / ".config/systemd/user/sebastian.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[Unit]\n")
    calls: list[list[str]] = []

    def fake_run(cmd, *_args, **_kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="active\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.restart()

    assert ["systemctl", "--user", "restart", "sebastian.service"] in calls


def test_restart_launchd_service_stops_and_starts(
    macos_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    plist = macos_env / "Library/LaunchAgents/com.sebastian.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text("<plist/>")
    calls: list[list[str]] = []

    def fake_run(cmd, *_args, **_kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.restart()

    assert ["launchctl", "stop", "com.sebastian"] in calls
    assert ["launchctl", "start", "com.sebastian"] in calls


def test_restart_launchd_starts_when_stop_reports_not_running(
    macos_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    plist = macos_env / "Library/LaunchAgents/com.sebastian.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text("<plist/>")
    calls: list[list[str]] = []

    def fake_run(cmd, *_args, **_kwargs):
        calls.append(cmd)
        if cmd == ["launchctl", "stop", "com.sebastian"]:
            return MagicMock(returncode=3, stdout="", stderr="not running")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.restart()

    assert calls == [
        ["launchctl", "stop", "com.sebastian"],
        ["launchctl", "start", "com.sebastian"],
    ]


def test_uninstall_removes_unit_on_linux(linux_env: Path) -> None:
    from sebastian.cli import service

    unit = linux_env / ".config/systemd/user/sebastian.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[old]")

    with patch.object(service.subprocess, "run", return_value=MagicMock(returncode=0)):
        service.uninstall()

    assert not unit.exists()
