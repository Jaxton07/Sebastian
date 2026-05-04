# Service Update And Status Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sebastian status`, `sebastian update`, and version reporting match the service modes users actually install, especially systemd/launchd auto-start services.

**Architecture:** Keep one source of truth for service-manager detection in `sebastian.cli.service`, then have `sebastian status` and `sebastian update` consult it before falling back to legacy PID-file daemon behavior. Add a lightweight version helper used by both `sebastian version` and `sebastian --version` so users have a stable way to confirm what is installed and what is running.

**Tech Stack:** Python 3.12, Typer CLI, user-level systemd, launchd, pytest, unittest.mock.

---

## Problem Summary

Today Sebastian has two runtime modes:

- Legacy daemon mode: `sebastian serve --daemon`, which writes `~/.sebastian/run/sebastian.pid`.
- Service mode: `sebastian service install`, which writes a systemd user unit on Linux or launchd plist on macOS. The unit currently runs `sebastian serve`, not `sebastian serve --daemon`, so it does not write the PID file.

This causes three user-visible issues:

- `sebastian status` says "Sebastian 未在运行" while `systemctl --user status sebastian` shows the service is running.
- `sebastian update` only checks the PID file, so it does not restart a running systemd/launchd service after replacing the installed files.
- Users expect `sebastian --version` or `sebastian version`, but no stable version command exists.

Do not change the service template to use `serve --daemon`. systemd/launchd should supervise the foreground process directly. The fix is to make CLI status/update service-aware.

## File Structure

- Modify `sebastian/cli/service.py`
  - Own service manager detection and restart operations.
  - Add non-Typer helpers for `is_installed`, `is_active`, `restart`, and structured status.
- Modify `sebastian/cli/updater.py`
  - Replace PID-only auto-restart with service-aware restart: active service first, legacy daemon second.
  - Print precise post-update guidance when no running process is detected.
- Modify `sebastian/main.py`
  - Add `sebastian version`.
  - Add `sebastian --version`.
  - Make top-level `sebastian status` show service status when service mode is installed, then legacy daemon status.
- Modify `sebastian/cli/README.md`
  - Document service-aware status/update behavior and version commands.
- Modify `README.md`
  - Update user-facing operational commands: status, restart, update, version.
- Modify `docs/AGENTIC_DEPLOYMENT.md`
  - Update deployment agent instructions so agents use `sebastian service status` or top-level `sebastian status`, and know update restarts service-managed installs.
- Test `tests/unit/test_service_install.py`
  - Extend service tests for status/restart helpers on Linux and macOS.
- Test `tests/unit/runtime/test_updater.py`
  - Add update restart tests for active systemd/launchd service, legacy daemon fallback, and no-running-process guidance.
- Test `tests/unit/runtime/test_cli_main.py`
  - Add CLI-level tests for `version`, `--version`, and service-aware top-level `status`.

## Task 1: Add Service State Helpers

**Files:**
- Modify: `sebastian/cli/service.py`
- Test: `tests/unit/test_service_install.py`

- [ ] **Step 1: Write failing Linux service helper tests**

Add tests near existing service tests:

```python
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
    assert state.status_text == "systemd user service: active"
```

Also add a macOS launchd test:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_service_install.py::test_systemd_service_state_reports_installed_and_active tests/unit/test_service_install.py::test_launchd_service_state_reports_loaded -q
```

Expected: FAIL because `get_service_state` does not exist.

- [ ] **Step 3: Implement minimal service state data model**

In `sebastian/cli/service.py`, add:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceState:
    kind: str
    installed: bool
    active: bool
    status_text: str
```

Add helpers:

```python
def get_service_state() -> ServiceState:
    if sys.platform.startswith("linux"):
        return _systemd_state()
    if sys.platform == "darwin":
        return _launchd_state()
    raise _platform_unsupported()


def is_service_installed() -> bool:
    try:
        return get_service_state().installed
    except ServiceError:
        return False


def is_service_active() -> bool:
    try:
        state = get_service_state()
    except ServiceError:
        return False
    return state.installed and state.active
```

Implement Linux:

```python
def _systemd_state() -> ServiceState:
    unit = _systemd_unit_path()
    if not unit.exists():
        return ServiceState(
            kind="systemd",
            installed=False,
            active=False,
            status_text="systemd user service: not installed",
        )
    proc = subprocess.run(
        ["systemctl", "--user", "is-active", "sebastian.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    state = proc.stdout.strip() or proc.stderr.strip() or "unknown"
    return ServiceState(
        kind="systemd",
        installed=True,
        active=(state == "active"),
        status_text=f"systemd user service: {state}",
    )
```

Implement macOS:

```python
def _launchd_state() -> ServiceState:
    plist = _launchd_plist_path()
    if not plist.exists():
        return ServiceState(
            kind="launchd",
            installed=False,
            active=False,
            status_text="launchd: not installed",
        )
    proc = subprocess.run(
        ["launchctl", "list", "com.sebastian"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ServiceState(
            kind="launchd",
            installed=True,
            active=False,
            status_text="launchd: installed but not loaded",
        )
    return ServiceState(
        kind="launchd",
        installed=True,
        active=True,
        status_text=f"launchd:\n{proc.stdout}",
    )
```

Then make existing `status()` delegate:

```python
def status() -> str:
    return get_service_state().status_text
```

- [ ] **Step 4: Run service helper tests**

Run:

```bash
pytest tests/unit/test_service_install.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/cli/service.py tests/unit/test_service_install.py
git commit -m "feat(cli): expose service state helpers"
```

## Task 2: Add Service Restart Helper

**Files:**
- Modify: `sebastian/cli/service.py`
- Test: `tests/unit/test_service_install.py`

- [ ] **Step 1: Write failing restart tests**

Add Linux restart test:

```python
def test_restart_systemd_service_uses_systemctl(
    linux_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    unit = linux_env / ".config/systemd/user/sebastian.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[Unit]\n")
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="active\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.restart()

    assert ["systemctl", "--user", "restart", "sebastian.service"] in calls
```

Add macOS restart test:

```python
def test_restart_launchd_service_stops_and_starts(
    macos_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.cli import service

    plist = macos_env / "Library/LaunchAgents/com.sebastian.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text("<plist/>")
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.restart()

    assert ["launchctl", "stop", "com.sebastian"] in calls
    assert ["launchctl", "start", "com.sebastian"] in calls
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_service_install.py::test_restart_systemd_service_uses_systemctl tests/unit/test_service_install.py::test_restart_launchd_service_stops_and_starts -q
```

Expected: FAIL because `restart` does not exist.

- [ ] **Step 3: Implement restart**

In `sebastian/cli/service.py`, add:

```python
def restart() -> None:
    if sys.platform.startswith("linux"):
        _run(["systemctl", "--user", "restart", "sebastian.service"])
    elif sys.platform == "darwin":
        _run(["launchctl", "stop", "com.sebastian"])
        _run(["launchctl", "start", "com.sebastian"])
    else:
        raise _platform_unsupported()
```

Add Typer command:

```python
@app.command("restart")
def cmd_restart() -> None:
    """重启 Sebastian 系统服务。"""
    try:
        restart()
    except ServiceError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo("✓ Sebastian 系统服务已重启")
```

- [ ] **Step 4: Run service tests**

Run:

```bash
pytest tests/unit/test_service_install.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/cli/service.py tests/unit/test_service_install.py
git commit -m "feat(cli): add service restart command"
```

## Task 3: Make `sebastian update` Restart Service-Managed Installs

**Files:**
- Modify: `sebastian/cli/updater.py`
- Test: `tests/unit/runtime/test_updater.py`

- [ ] **Step 1: Write failing updater tests**

In `tests/unit/runtime/test_updater.py`, add tests for the private restart helper. Use monkeypatching rather than running real systemd/launchd.

```python
def test_try_restart_daemon_restarts_active_service(monkeypatch, tmp_path: Path) -> None:
    from sebastian.cli import updater

    messages: list[str] = []

    monkeypatch.setattr("sebastian.cli.service.is_service_active", lambda: True)
    restart = MagicMock()
    monkeypatch.setattr("sebastian.cli.service.restart", restart)

    updater._try_restart_daemon(messages.append)

    restart.assert_called_once_with()
    assert any("系统服务已重启" in message for message in messages)
```

Add fallback test:

```python
def test_try_restart_daemon_falls_back_to_pid_daemon(monkeypatch, tmp_path: Path) -> None:
    from sebastian.cli import updater

    messages: list[str] = []

    monkeypatch.setattr("sebastian.cli.service.is_service_active", lambda: False)
    monkeypatch.setattr("sebastian.config.settings.run_dir", tmp_path)
    monkeypatch.setattr("sebastian.cli.daemon.read_pid", lambda path: 123)
    monkeypatch.setattr("sebastian.cli.daemon.is_running", lambda pid: True)
    stop = MagicMock()
    monkeypatch.setattr("sebastian.cli.daemon.stop_process", stop)
    run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(updater.subprocess, "run", run)

    updater._try_restart_daemon(messages.append)

    stop.assert_called_once()
    assert run.call_args.args[0][-3:] == ["sebastian", "serve", "--daemon"]
```

Add no-running-service guidance test:

```python
def test_try_restart_daemon_prints_service_guidance_when_service_installed_but_inactive(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from sebastian.cli import updater

    messages: list[str] = []

    monkeypatch.setattr("sebastian.cli.service.is_service_active", lambda: False)
    monkeypatch.setattr("sebastian.cli.service.is_service_installed", lambda: True)
    monkeypatch.setattr("sebastian.config.settings.run_dir", tmp_path)
    monkeypatch.setattr("sebastian.cli.daemon.read_pid", lambda path: None)

    updater._try_restart_daemon(messages.append)

    assert any("sebastian service start" in message for message in messages)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/runtime/test_updater.py::test_try_restart_daemon_restarts_active_service tests/unit/runtime/test_updater.py::test_try_restart_daemon_falls_back_to_pid_daemon tests/unit/runtime/test_updater.py::test_try_restart_daemon_prints_service_guidance_when_service_installed_but_inactive -q
```

Expected: first and third tests fail because `_try_restart_daemon` is PID-only.

- [ ] **Step 3: Implement service-aware restart in updater**

Modify `_try_restart_daemon` in `sebastian/cli/updater.py`:

```python
def _try_restart_daemon(printer: Callable[[str], None]) -> None:
    """Restart active service-managed or legacy daemon process after update."""
    from sebastian.cli import service
    from sebastian.cli.daemon import is_running, pid_path, read_pid, stop_process
    from sebastian.config import settings

    if service.is_service_active():
        printer("→ 检测到 Sebastian 系统服务，正在重启...")
        try:
            service.restart()
        except service.ServiceError as exc:
            printer(f"⚠ 系统服务重启失败：{exc}")
            printer("请手动运行 `sebastian service restart` 或 `systemctl --user restart sebastian`。")
            return
        printer("✓ Sebastian 系统服务已重启")
        return

    pf = pid_path(settings.run_dir)
    pid = read_pid(pf)
    if pid is not None and is_running(pid):
        printer(f"→ 检测到后台进程 (PID {pid})，正在重启...")
        stop_process(pf)
        cmd = [sys.executable, "-m", "sebastian", "serve", "--daemon"]
        proc = subprocess.run(cmd, check=False)
        if proc.returncode == 0:
            printer("✓ 后台进程已重启")
        else:
            printer("⚠ 自动重启失败，请手动运行 `sebastian serve -d`。")
        return

    if service.is_service_installed():
        printer("提示：Sebastian 系统服务已安装但当前未运行。")
        printer("如需启动新版本，请运行 `sebastian service start`。")
    else:
        printer("提示：未检测到后台进程，请手动运行 `sebastian serve`。")
```

- [ ] **Step 4: Run updater tests**

Run:

```bash
pytest tests/unit/runtime/test_updater.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/cli/updater.py tests/unit/runtime/test_updater.py
git commit -m "fix(cli): update restarts service-managed installs"
```

## Task 4: Make Top-Level `sebastian status` Service-Aware

**Files:**
- Modify: `sebastian/main.py`
- Test: `tests/unit/runtime/test_cli_main.py`

- [ ] **Step 1: Create failing CLI status tests**

Create `tests/unit/runtime/test_cli_main.py` if it does not exist:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from sebastian.main import app

runner = CliRunner()
```

Add service-aware status test:

```python
def test_status_reports_active_service(monkeypatch) -> None:
    monkeypatch.setattr("sebastian.cli.service.is_service_installed", lambda: True)
    monkeypatch.setattr("sebastian.cli.service.status", lambda: "systemd user service: active")

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "systemd user service: active" in result.output
```

Add legacy daemon fallback test:

```python
def test_status_falls_back_to_legacy_pid_daemon(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sebastian.cli.service.is_service_installed", lambda: False)
    monkeypatch.setattr("sebastian.config.settings.run_dir", tmp_path)
    monkeypatch.setattr("sebastian.cli.daemon.read_pid", lambda path: 456)
    monkeypatch.setattr("sebastian.cli.daemon.is_running", lambda pid: True)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "PID 456" in result.output
```

- [ ] **Step 2: Run tests to verify first one fails**

Run:

```bash
pytest tests/unit/runtime/test_cli_main.py::test_status_reports_active_service tests/unit/runtime/test_cli_main.py::test_status_falls_back_to_legacy_pid_daemon -q
```

Expected: service-aware test fails because top-level status does not inspect service state.

- [ ] **Step 3: Implement service-aware top-level status**

Modify `status()` in `sebastian/main.py`:

```python
@app.command()
def status() -> None:
    """Check whether Sebastian is running."""
    from sebastian.cli import service
    from sebastian.cli.daemon import is_running, pid_path, read_pid, remove_pid
    from sebastian.config import settings

    if service.is_service_installed():
        try:
            typer.echo(service.status())
            return
        except service.ServiceError as exc:
            typer.echo(f"⚠ 服务状态检查失败：{exc}", err=True)

    pf = pid_path(settings.run_dir)
    pid = read_pid(pf)
    if pid and is_running(pid):
        typer.echo(f"✓ Sebastian 正在运行 (PID {pid})")
    else:
        typer.echo("Sebastian 未在运行")
        if pid:
            remove_pid(pf)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/unit/runtime/test_cli_main.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/main.py tests/unit/runtime/test_cli_main.py
git commit -m "fix(cli): make status service-aware"
```

## Task 5: Add Version Commands

**Files:**
- Modify: `sebastian/main.py`
- Test: `tests/unit/runtime/test_cli_main.py`

- [ ] **Step 1: Write failing version tests**

Add tests:

```python
def test_version_command_prints_installed_version(monkeypatch) -> None:
    monkeypatch.setattr("sebastian.main._resolve_version", lambda: "9.8.7")

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "9.8.7" in result.output
```

```python
def test_global_version_option_prints_installed_version(monkeypatch) -> None:
    monkeypatch.setattr("sebastian.main._resolve_version", lambda: "9.8.7")

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "9.8.7" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/runtime/test_cli_main.py::test_version_command_prints_installed_version tests/unit/runtime/test_cli_main.py::test_global_version_option_prints_installed_version -q
```

Expected: FAIL because neither version path exists.

- [ ] **Step 3: Implement shared version helper**

In `sebastian/main.py`, add helper near app construction:

```python
def _resolve_version() -> str:
    import importlib.metadata
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as file:
            version = tomllib.load(file)["project"]["version"]
            return str(version)
    return importlib.metadata.version("sebastian")
```

Update existing `serve()` startup banner to use `_resolve_version()` instead of duplicating pyproject parsing.

Add Typer callback:

```python
@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Print Sebastian version and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        typer.echo(f"Sebastian v{_resolve_version()}")
        raise typer.Exit()
```

Add explicit command:

```python
@app.command("version")
def version_cmd() -> None:
    """Print Sebastian version."""
    typer.echo(f"Sebastian v{_resolve_version()}")
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/unit/runtime/test_cli_main.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/main.py tests/unit/runtime/test_cli_main.py
git commit -m "feat(cli): add version commands"
```

## Task 6: Polish Service Command Output

**Files:**
- Modify: `sebastian/cli/service.py`
- Test: `tests/unit/test_service_install.py`

- [ ] **Step 1: Write failing service status detail test**

Add a test that catches the exact user confusion:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/unit/test_service_install.py::test_systemd_status_output_suggests_correct_commands -q
```

Expected: FAIL because status currently only returns one line.

- [ ] **Step 3: Add concise command hints to service status**

Adjust `_systemd_state()` to produce:

```python
status_text=(
    f"systemd user service: {state}\n"
    "  status:  systemctl --user status sebastian\n"
    "  restart: sebastian service restart"
)
```

Adjust `_launchd_state()` similarly, but use launchd commands:

```python
status_text=(
    "launchd: installed but not loaded\n"
    "  status:  launchctl list com.sebastian\n"
    "  restart: sebastian service restart"
)
```

Keep output short. Do not dump long service logs from top-level `sebastian status`; `sebastian service status` can continue appending recent `service.err.log`.

- [ ] **Step 4: Run service tests**

Run:

```bash
pytest tests/unit/test_service_install.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/cli/service.py tests/unit/test_service_install.py
git commit -m "chore(cli): clarify service status output"
```

## Task 7: Update Docs And README Indexes

**Files:**
- Modify: `sebastian/cli/README.md`
- Modify: `sebastian/README.md`
- Modify: `README.md`
- Modify: `docs/AGENTIC_DEPLOYMENT.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update CLI README**

In `sebastian/cli/README.md`, update:

- Directory structure includes `service.py` and `service_templates.py`.
- `updater.py` step 9 says:
  - active systemd/launchd service is restarted first;
  - legacy PID daemon is restarted second;
  - otherwise update prints exact start guidance.
- CLI command table includes:
  - `sebastian version`
  - `sebastian --version`
  - `sebastian service restart`
  - `sebastian service status`

- [ ] **Step 2: Update backend README**

In `sebastian/README.md`, under `cli/`, document:

```text
- `main.py`：Typer CLI 入口；`serve/status/update/version` 顶层命令；挂载 `service` 子命令。
- `cli/service.py`：systemd/launchd 服务安装、状态、重启。
```

- [ ] **Step 3: Update root README operational commands**

In `README.md`, add a short operations snippet:

```bash
sebastian version
sebastian status
sebastian service status
sebastian update
```

State that service-managed installs restart automatically after update.

- [ ] **Step 4: Update agentic deployment guide**

In `docs/AGENTIC_DEPLOYMENT.md`, replace any instruction that treats `sebastian status` as PID-only. Add:

```text
If auto-start service was installed, prefer `sebastian service status` for service diagnostics.
After `sebastian update`, Sebastian restarts an active systemd/launchd service automatically.
If the service is installed but inactive, run `sebastian service start`.
```

- [ ] **Step 5: Update CHANGELOG**

Add under `[Unreleased]`:

```markdown
### Changed
- `sebastian status` 和 `sebastian update` 现在识别 systemd/launchd 服务模式，避免开机自启服务运行中却显示未运行，升级后也会自动重启 active 服务。

### Added
- 新增 `sebastian version` / `sebastian --version`，方便部署和升级后确认当前版本。
```

- [ ] **Step 6: Run docs grep sanity check**

Run:

```bash
python - <<'PY'
from pathlib import Path
for path in [Path("README.md"), Path("docs/AGENTIC_DEPLOYMENT.md"), Path("sebastian/cli/README.md")]:
    text = path.read_text()
    assert "sebastian version" in text or path.name == "AGENTIC_DEPLOYMENT.md"
print("docs sanity ok")
PY
```

Expected: `docs sanity ok`.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/AGENTIC_DEPLOYMENT.md sebastian/README.md sebastian/cli/README.md CHANGELOG.md
git commit -m "docs(cli): clarify service update workflow"
```

## Task 8: Full Verification

**Files:**
- No code changes unless verification reveals a bug.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
pytest tests/unit/test_service_install.py tests/unit/runtime/test_updater.py tests/unit/runtime/test_cli_main.py -q
```

Expected: PASS.

- [ ] **Step 2: Run backend lint and type checks**

Run:

```bash
ruff check sebastian/ tests/
ruff format --check sebastian/ tests/
mypy sebastian/
```

Expected: all pass.

- [ ] **Step 3: Run full Python test suite**

Run:

```bash
pytest tests/unit tests/integration -q
```

Expected: PASS.

- [ ] **Step 4: Rebuild graphify code graph**

Run:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: graph rebuild completes and updates `graphify-out`.

- [ ] **Step 5: Manual Linux service smoke test**

On a Linux host with Sebastian installed as user service:

```bash
sebastian version
sebastian status
sebastian service status
sebastian update --check
```

Expected:

- `sebastian version` prints the installed version.
- `sebastian status` reports `systemd user service: active` when systemd service is active.
- `sebastian service status` reports service status and recent service error log if present.
- `sebastian update --check` does not change service state.

- [ ] **Step 6: Manual update restart smoke test**

On a Linux host with active user service:

```bash
before="$(systemctl --user show sebastian.service -P ActiveEnterTimestamp)"
sebastian update --force --yes
after="$(systemctl --user show sebastian.service -P ActiveEnterTimestamp)"
printf 'before=%s\nafter=%s\n' "$before" "$after"
```

Expected:

- `sebastian update` prints `✓ Sebastian 系统服务已重启`.
- `after` is newer than `before`.
- `systemctl --user status sebastian` shows active running.

- [ ] **Step 7: Final commit if verification fixes were needed**

If verification caused fixes:

```bash
git add <specific files>
git commit -m "fix(cli): address service update verification"
```

## Acceptance Criteria

- `sebastian status` no longer misreports "未在运行" when a systemd/launchd service is installed and active.
- `sebastian update` restarts an active systemd/launchd service after successful update.
- Legacy `sebastian serve --daemon` PID-file restart still works.
- If a service is installed but inactive, update prints `sebastian service start` guidance.
- `sebastian version` and `sebastian --version` both work.
- Service status output includes the correct command family, preventing confusion with `service sebastian update`.
- Docs teach users and deployment agents the correct operational commands.
- Focused tests, lint, mypy, full Python tests, and graphify rebuild pass.

## Notes For Implementers

- Do not introduce sudo flows. `sebastian service` manages user-level systemd units and launchd agents only.
- Do not make systemd run `serve --daemon`; service managers should supervise foreground processes.
- Do not rely on `service sebastian ...`; that is a different Linux command family and is not the Sebastian CLI.
- Keep this feature CLI-only. It should not touch gateway, Android, browser tools, memory, or LLM code.
- Use exact-file `git add`; do not use `git add .`.
