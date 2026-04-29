from __future__ import annotations

from pathlib import Path

import pytest


def test_macos_backend_builds_screencapture_command(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.screenshot_send import _select_capture_command

    output = tmp_path / "shot.png"

    command = _select_capture_command(
        system="Darwin",
        env={},
        which=lambda name: f"/usr/bin/{name}" if name == "screencapture" else None,
        output_path=output,
    )

    assert command == ["/usr/sbin/screencapture", "-x", str(output)]


def test_linux_x11_prefers_gnome_screenshot(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.screenshot_send import _select_capture_command

    output = tmp_path / "shot.png"

    command = _select_capture_command(
        system="Linux",
        env={"DISPLAY": ":0"},
        which=lambda name: f"/usr/bin/{name}" if name in {"gnome-screenshot", "scrot"} else None,
        output_path=output,
    )

    assert command == ["/usr/bin/gnome-screenshot", "-f", str(output)]


def test_linux_x11_falls_back_to_scrot(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.screenshot_send import _select_capture_command

    output = tmp_path / "shot.png"

    command = _select_capture_command(
        system="Linux",
        env={"DISPLAY": ":0"},
        which=lambda name: "/usr/bin/scrot" if name == "scrot" else None,
        output_path=output,
    )

    assert command == ["/usr/bin/scrot", str(output)]


def test_linux_wayland_uses_grim(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.screenshot_send import _select_capture_command

    output = tmp_path / "shot.png"

    command = _select_capture_command(
        system="Linux",
        env={"WAYLAND_DISPLAY": "wayland-0"},
        which=lambda name: "/usr/bin/grim" if name == "grim" else None,
        output_path=output,
    )

    assert command == ["/usr/bin/grim", str(output)]


def test_linux_wayland_and_x11_prefers_wayland(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.screenshot_send import _select_capture_command

    output = tmp_path / "shot.png"

    def which(name: str) -> str | None:
        return {
            "grim": "/usr/bin/grim",
            "gnome-screenshot": "/usr/bin/gnome-screenshot",
            "scrot": "/usr/bin/scrot",
        }.get(name)

    command = _select_capture_command(
        system="Linux",
        env={"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"},
        which=which,
        output_path=output,
    )

    assert command == ["/usr/bin/grim", str(output)]


def test_linux_headless_raises_error(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.screenshot_send import _select_capture_command

    with pytest.raises(RuntimeError, match="DISPLAY/WAYLAND_DISPLAY is missing"):
        _select_capture_command(
            system="Linux",
            env={},
            which=lambda name: None,
            output_path=tmp_path / "shot.png",
        )


def test_linux_missing_backends_raises_error(tmp_path: Path) -> None:
    from sebastian.capabilities.tools.screenshot_send import _select_capture_command

    with pytest.raises(RuntimeError, match="No supported Linux screenshot backend found"):
        _select_capture_command(
            system="Linux",
            env={"DISPLAY": ":0"},
            which=lambda name: None,
            output_path=tmp_path / "shot.png",
        )
