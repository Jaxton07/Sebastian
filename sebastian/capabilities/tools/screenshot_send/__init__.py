from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path


DESCRIPTION = (
    "Capture a screenshot of the backend host machine's screen and send it to the "
    "current conversation. This captures the server desktop, not the Android device screen."
)


def _select_capture_command(
    *,
    system: str,
    env: Mapping[str, str],
    which: Callable[[str], str | None],
    output_path: Path,
) -> list[str]:
    if system == "Darwin":
        return ["/usr/sbin/screencapture", "-x", str(output_path)]

    if system != "Linux":
        raise RuntimeError(
            f"Unsupported screenshot platform: {system}. Do not retry automatically; "
            "tell the user screenshots are only supported on macOS and Linux backend hosts."
        )

    if env.get("WAYLAND_DISPLAY"):
        grim = which("grim")
        if grim:
            return [grim, str(output_path)]
        raise RuntimeError(
            "No supported Linux screenshot backend found for Wayland. Do not retry automatically; "
            "ask the user to install grim or use a supported desktop session."
        )

    if env.get("DISPLAY"):
        gnome_screenshot = which("gnome-screenshot")
        if gnome_screenshot:
            return [gnome_screenshot, "-f", str(output_path)]
        scrot = which("scrot")
        if scrot:
            return [scrot, str(output_path)]
        raise RuntimeError(
            "No supported Linux screenshot backend found. Do not retry automatically; "
            "ask the user to install gnome-screenshot, scrot, or grim for their desktop session."
        )

    raise RuntimeError(
        "Linux screenshot requires a graphical session; DISPLAY/WAYLAND_DISPLAY is missing. "
        "Do not retry automatically; tell the user screenshots are unavailable in this headless session."
    )
