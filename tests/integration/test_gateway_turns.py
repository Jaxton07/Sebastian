from __future__ import annotations

import importlib
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("SEBASTIAN_JWT_SECRET", "test-secret-key")
os.environ.setdefault("SEBASTIAN_DATA_DIR", "/tmp/sebastian_test")


@pytest.fixture
def client(tmp_path):
    from sebastian.core.types import Session
    from sebastian.gateway.auth import hash_password

    password_hash = hash_password("testpass")
    fake_session = Session(agent="sebastian", title="Test session")

    with patch.dict(
        os.environ,
        {
            "SEBASTIAN_OWNER_PASSWORD_HASH": password_hash,
            "SEBASTIAN_DATA_DIR": str(tmp_path),
            "ANTHROPIC_API_KEY": "test-key-not-real",
            "SEBASTIAN_JWT_SECRET": "test-secret-key",
        },
    ):
        import sebastian.config as cfg_module

        importlib.reload(cfg_module)

        with patch.object(
            cfg_module.settings, "sebastian_owner_password_hash", password_hash
        ):
            with patch(
                "sebastian.orchestrator.sebas.Sebastian.chat",
                new_callable=AsyncMock,
                return_value="Mocked response from Sebastian.",
            ) as mock_chat:
                with patch(
                    "sebastian.orchestrator.sebas.Sebastian.get_or_create_session",
                    new_callable=AsyncMock,
                    return_value=fake_session,
                ):
                    from sebastian.gateway.app import create_app
                    from starlette.testclient import TestClient

                    test_app = create_app()
                    with TestClient(test_app, raise_server_exceptions=True) as test_client:
                        yield test_client, mock_chat, fake_session


def _login(client) -> str:
    response = client.post("/api/v1/auth/login", json={"password": "testpass"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_health_endpoint(client):
    http_client, _, _ = client
    response = http_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_success(client):
    http_client, _, _ = client
    token = _login(http_client)
    assert len(token) > 10


def test_login_wrong_password(client):
    http_client, _, _ = client
    response = http_client.post("/api/v1/auth/login", json={"password": "wrongpass"})
    assert response.status_code == 401


def test_send_turn_requires_auth(client):
    http_client, _, _ = client
    response = http_client.post("/api/v1/turns", json={"content": "hello"})
    assert response.status_code in (401, 403)


def test_send_turn_returns_response(client):
    http_client, mock_chat, fake_session = client
    token = _login(http_client)
    response = http_client.post(
        "/api/v1/turns",
        json={"content": "Hello Sebastian"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["response"] == "Mocked response from Sebastian."
    assert data["session_id"] == fake_session.id
    mock_chat.assert_awaited_once_with("Hello Sebastian", fake_session.id)
