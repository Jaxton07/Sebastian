from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


def test_settings_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Settings should load with sane defaults even without a .env file."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from sebastian.config import Settings

    s = Settings()
    assert s.sebastian_gateway_port == 8823
    assert s.sebastian_jwt_algorithm == "HS256"
    assert s.sebastian_owner_name == "Owner"
    assert "sqlite" in s.database_url


def test_database_url_uses_data_dir(tmp_path: Path) -> None:
    """database_url should embed the data dir path."""
    from sebastian.config import Settings

    s = Settings(sebastian_data_dir=str(tmp_path))
    assert str(tmp_path) in s.database_url


def test_module_settings_loads_explicit_user_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "installed.env"
    data_dir = tmp_path / "sebastian-data"
    env_file.write_text(
        "\n".join(
            [
                "SEBASTIAN_OWNER_NAME=Installed Owner",
                f"SEBASTIAN_DATA_DIR={data_dir}",
                "SEBASTIAN_BROWSER_UPSTREAM_PROXY=http://127.0.0.1:7890",
            ]
        )
    )
    monkeypatch.setenv("SEBASTIAN_ENV_FILE", str(env_file))
    monkeypatch.delenv("SEBASTIAN_OWNER_NAME", raising=False)
    monkeypatch.delenv("SEBASTIAN_DATA_DIR", raising=False)
    monkeypatch.delenv("SEBASTIAN_BROWSER_UPSTREAM_PROXY", raising=False)

    import sebastian.config as config

    try:
        config = importlib.reload(config)

        assert config.settings.sebastian_owner_name == "Installed Owner"
        assert config.settings.data_dir == data_dir.resolve()
        assert config.settings.sebastian_browser_upstream_proxy == "http://127.0.0.1:7890"
    finally:
        monkeypatch.delenv("SEBASTIAN_ENV_FILE", raising=False)
        importlib.reload(config)


def test_module_settings_real_env_overrides_user_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "installed.env"
    env_file.write_text("SEBASTIAN_BROWSER_UPSTREAM_PROXY=http://file-proxy:7890\n")
    monkeypatch.setenv("SEBASTIAN_ENV_FILE", str(env_file))
    monkeypatch.setenv("SEBASTIAN_BROWSER_UPSTREAM_PROXY", "http://env-proxy:7890")

    import sebastian.config as config

    try:
        config = importlib.reload(config)

        assert config.settings.sebastian_browser_upstream_proxy == "http://env-proxy:7890"
    finally:
        monkeypatch.delenv("SEBASTIAN_ENV_FILE", raising=False)
        monkeypatch.delenv("SEBASTIAN_BROWSER_UPSTREAM_PROXY", raising=False)
        importlib.reload(config)


def test_jwt_create_and_decode() -> None:
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    from sebastian.gateway.auth import create_access_token, decode_token

    token = create_access_token({"sub": "owner", "role": "owner"})
    assert isinstance(token, str)
    payload = decode_token(token)
    assert payload["sub"] == "owner"
    assert payload["role"] == "owner"


def test_jwt_invalid_token_raises() -> None:
    from fastapi import HTTPException

    from sebastian.gateway.auth import decode_token

    with pytest.raises(HTTPException) as exc_info:
        decode_token("not.a.valid.token")
    assert exc_info.value.status_code == 401


def test_hash_and_verify_password() -> None:
    from sebastian.gateway.auth import hash_password, verify_password

    hashed = hash_password("secretpassword")
    assert verify_password("secretpassword", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_log_settings_defaults() -> None:
    """日志开关默认值应为 False。"""
    from sebastian.config import Settings

    s = Settings()
    assert s.sebastian_log_llm_stream is False
    assert s.sebastian_log_sse is False


def test_log_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """环境变量应能覆盖日志开关默认值。"""
    monkeypatch.setenv("SEBASTIAN_LOG_LLM_STREAM", "true")
    monkeypatch.setenv("SEBASTIAN_LOG_SSE", "true")
    from sebastian.config import Settings

    s = Settings()
    assert s.sebastian_log_llm_stream is True
    assert s.sebastian_log_sse is True


def test_browser_settings_defaults() -> None:
    from sebastian.config import Settings

    s = Settings(_env_file=None)
    assert s.sebastian_browser_headless is True
    assert s.sebastian_browser_viewport == "1280x900"
    assert s.sebastian_browser_timeout_ms == 30000
    assert s.sebastian_browser_dns_mode == "auto"
    assert s.sebastian_browser_doh_endpoint.startswith("https://")
    assert s.sebastian_browser_doh_timeout_ms == 5000
    assert s.sebastian_browser_upstream_proxy == ""


def test_browser_directory_properties_use_data_dir(tmp_path: Path) -> None:
    from sebastian.config import Settings

    s = Settings(sebastian_data_dir=str(tmp_path))

    assert s.browser_dir == tmp_path / "data" / "browser"
    assert s.browser_profile_dir == s.browser_dir / "profile"
    assert s.browser_downloads_dir == s.browser_dir / "downloads"
    assert s.browser_screenshots_dir == s.browser_dir / "screenshots"


def test_ensure_data_dir_creates_browser_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import sebastian.config as config
    from sebastian.config import Settings

    monkeypatch.setattr(config, "settings", Settings(sebastian_data_dir=str(tmp_path)))

    config.ensure_data_dir()

    assert config.settings.browser_profile_dir.is_dir()
    assert config.settings.browser_downloads_dir.is_dir()
    assert config.settings.browser_screenshots_dir.is_dir()
