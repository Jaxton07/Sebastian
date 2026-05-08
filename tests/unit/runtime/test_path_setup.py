from __future__ import annotations

import shlex
from pathlib import Path

from sebastian.cli.path_setup import ensure_cli_path


def test_ensure_cli_path_creates_shim_for_default_install(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    install_dir = home / ".sebastian" / "app"
    target = install_dir / ".venv" / "bin" / "sebastian"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n")
    target.chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("SEBASTIAN_SKIP_PATH_SETUP", raising=False)

    result = ensure_cli_path(install_dir=install_dir, update_shell_rc=False)

    shim = home / ".sebastian" / "bin" / "sebastian"
    assert shim.is_file()
    assert str(target) in shim.read_text()
    assert shim.stat().st_mode & 0o111
    assert result.shim_path == shim


def test_ensure_cli_path_shell_quotes_shim_target(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    install_dir = home / ".sebastian" / 'app "quoted"'
    target = install_dir / ".venv" / "bin" / "sebastian"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n")
    monkeypatch.setenv("HOME", str(home))

    ensure_cli_path(install_dir=install_dir, update_shell_rc=False)

    shim = home / ".sebastian" / "bin" / "sebastian"
    exec_line = shim.read_text().splitlines()[1]
    assert exec_line.startswith('exec "')
    assert exec_line.endswith('" "$@"')
    assert '\\"quoted\\"' in exec_line
    assert shlex.split(exec_line) == ["exec", str(target), "$@"]


def test_ensure_cli_path_updates_zshrc_once(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    install_dir = home / ".sebastian" / "app"
    (install_dir / ".venv" / "bin").mkdir(parents=True)
    (install_dir / ".venv" / "bin" / "sebastian").write_text("#!/bin/sh\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", "/bin/zsh")

    ensure_cli_path(install_dir=install_dir, update_shell_rc=True)
    ensure_cli_path(install_dir=install_dir, update_shell_rc=True)

    content = (home / ".zshrc").read_text()
    assert content.count("# >>> sebastian PATH >>>") == 1
    assert content.count("# <<< sebastian PATH <<<") == 1
    assert 'export PATH="$HOME/.sebastian/bin:$PATH"' in content


def test_skip_path_setup_skips_rc_but_not_shim(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    install_dir = home / ".sebastian" / "app"
    (install_dir / ".venv" / "bin").mkdir(parents=True)
    (install_dir / ".venv" / "bin" / "sebastian").write_text("#!/bin/sh\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setenv("SEBASTIAN_SKIP_PATH_SETUP", "1")

    ensure_cli_path(install_dir=install_dir, update_shell_rc=True)

    assert (home / ".sebastian" / "bin" / "sebastian").is_file()
    assert not (home / ".zshrc").exists()
