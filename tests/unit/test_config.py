from __future__ import annotations

import os
import pytest


def test_settings_defaults():
    """Settings should load with sane defaults even without a .env file."""
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    from sebastian.config import Settings

    s = Settings()
    assert s.sebastian_gateway_port == 8000
    assert s.sebastian_jwt_algorithm == "HS256"
    assert s.sebastian_owner_name == "Owner"
    assert "sqlite" in s.database_url


def test_database_url_uses_data_dir(tmp_path):
    """database_url should embed the data dir path."""
    from sebastian.config import Settings

    s = Settings(sebastian_data_dir=str(tmp_path))
    assert str(tmp_path) in s.database_url
