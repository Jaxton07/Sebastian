from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

START = "# >>> sebastian PATH >>>"
END = "# <<< sebastian PATH <<<"
EXPORT_LINE = 'export PATH="$HOME/.sebastian/bin:$PATH"'


@dataclass(frozen=True)
class PathSetupResult:
    shim_path: Path
    target_path: Path
    rc_files_updated: tuple[Path, ...]
    rc_skipped: bool


def ensure_cli_path(
    *,
    install_dir: Path,
    update_shell_rc: bool = True,
    home: Path | None = None,
) -> PathSetupResult:
    resolved_home = (home or Path.home()).expanduser()
    target = install_dir.expanduser().resolve() / ".venv" / "bin" / "sebastian"

    shim_dir = resolved_home / ".sebastian" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "sebastian"
    shim.write_text(
        f'#!/usr/bin/env sh\nexec "{_shell_double_quote_escape(str(target))}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)

    rc_skipped = os.environ.get("SEBASTIAN_SKIP_PATH_SETUP") == "1"
    updated: list[Path] = []
    if update_shell_rc and not rc_skipped:
        for rc_file in _target_rc_files(resolved_home):
            _upsert_path_block(rc_file)
            updated.append(rc_file)

    return PathSetupResult(
        shim_path=shim,
        target_path=target,
        rc_files_updated=tuple(updated),
        rc_skipped=rc_skipped,
    )


def _target_rc_files(home: Path) -> list[Path]:
    shell = os.environ.get("SHELL", "")
    if shell.endswith("zsh"):
        return [home / ".zshrc"]
    if shell.endswith("bash"):
        if os.uname().sysname == "Darwin":
            existing = [p for p in (home / ".bash_profile", home / ".bashrc") if p.exists()]
            return existing or [home / ".bash_profile"]
        return [home / ".bashrc"]
    return []


def _shell_double_quote_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )


def _upsert_path_block(path: Path) -> None:
    block = f"{START}\n{EXPORT_LINE}\n{END}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    start = existing.find(START)
    end = existing.find(END)
    if start != -1 and end != -1 and end > start:
        end += len(END)
        new_content = existing[:start] + block.rstrip("\n") + existing[end:]
        if not new_content.endswith("\n"):
            new_content += "\n"
        path.write_text(new_content, encoding="utf-8")
        return

    prefix = existing
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    path.write_text(prefix + block, encoding="utf-8")


def main() -> None:
    from sebastian.cli.updater import resolve_install_dir

    ensure_cli_path(install_dir=resolve_install_dir())


if __name__ == "__main__":
    main()
