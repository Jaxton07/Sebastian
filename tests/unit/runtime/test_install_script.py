from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def test_install_script_repairs_incomplete_venv(tmp_path: Path) -> None:
    project = tmp_path / "app"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile("scripts/install.sh", scripts / "install.sh")
    (scripts / "install.sh").chmod(0o755)

    # Simulate a previous failed install that left only the directory behind.
    (project / ".venv").mkdir()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls.log"
    (fake_bin / "python3").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "-c" ]]; then
  printf "3.12\\n"
  exit 0
fi
if [[ "$1" == "-m" && "$2" == "venv" && "$3" == ".venv" ]]; then
  printf "venv\\n" >> "$CALLS_LOG"
  mkdir -p .venv/bin
  cat > .venv/bin/activate <<'ACTIVATE'
export PATH="$PWD/.venv/bin:$PATH"
ACTIVATE
  cat > .venv/bin/pip <<'PIP'
#!/usr/bin/env bash
printf "pip %s\\n" "$*" >> "$CALLS_LOG"
PIP
  chmod +x .venv/bin/pip
  cat > .venv/bin/sebastian <<'SEBASTIAN'
#!/usr/bin/env bash
printf "sebastian %s\\n" "$*" >> "$CALLS_LOG"
SEBASTIAN
  chmod +x .venv/bin/sebastian
  exit 0
fi
exit 1
"""
    )
    (fake_bin / "python3").chmod(0o755)
    data_root = tmp_path / "custom-data-root"

    result = subprocess.run(
        [str(scripts / "install.sh")],
        cwd=project,
        env={
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "CALLS_LOG": str(calls),
            "HOME": str(tmp_path / "home"),
            "SEBASTIAN_DATA_DIR": str(data_root),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    log = calls.read_text()
    assert "venv\n" in log
    # macOS / 有 $DISPLAY → sebastian serve；headless Linux → sebastian init --headless
    assert ("sebastian serve" in log) or ("sebastian init --headless" in log)
    assert "service install" not in log
    env_file = data_root / ".env"
    assert env_file.is_file()
    env_content = env_file.read_text()
    assert f"SEBASTIAN_DATA_DIR={data_root}" in env_content
    assert "# SEBASTIAN_BROWSER_UPSTREAM_PROXY=http://127.0.0.1:7890" in env_content
    assert "# SEBASTIAN_BROWSER_DNS_MODE=auto" in env_content
