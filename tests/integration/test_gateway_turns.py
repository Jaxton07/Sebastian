from __future__ import annotations

import asyncio
import importlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("SEBASTIAN_JWT_SECRET", "test-secret-key")
os.environ.setdefault("SEBASTIAN_DATA_DIR", "/tmp/sebastian_test")


@pytest.fixture
def client(tmp_path):
    from sebastian.core.types import Session
    from sebastian.gateway.auth import hash_password

    password_hash = hash_password("testpass")
    fake_session = Session(
        agent_type="sebastian",
        agent_id="sebastian_01",
        title="Test session",
    )

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
                "sebastian.orchestrator.sebas.Sebastian.run_streaming",
                new_callable=AsyncMock,
                return_value="Mocked response from Sebastian.",
            ) as mock_run_streaming:
                with patch(
                    "sebastian.orchestrator.sebas.Sebastian.get_or_create_session",
                    new_callable=AsyncMock,
                    return_value=fake_session,
                ):
                    from starlette.testclient import TestClient

                    from sebastian.gateway.app import create_app

                    test_app = create_app()
                    with TestClient(test_app, raise_server_exceptions=True) as test_client:
                        yield test_client, mock_run_streaming, fake_session


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


def test_send_turn_returns_immediate_session_metadata(client):
    http_client, mock_run_streaming, fake_session = client
    token = _login(http_client)
    scheduled_coroutines = []

    def capture_background_task(coroutine):
        scheduled_coroutines.append(coroutine)
        coroutine.close()
        return MagicMock()

    with patch(
        "sebastian.gateway.routes.turns.asyncio.create_task",
        side_effect=capture_background_task,
    ) as mock_create_task:
        response = http_client.post(
            "/api/v1/turns",
            json={"content": "Hello Sebastian"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"] == fake_session.id
    assert "ts" in data
    assert "response" not in data
    assert len(scheduled_coroutines) == 1
    mock_create_task.assert_called_once()
    mock_run_streaming.assert_called_once_with("Hello Sebastian", fake_session.id)
    assert mock_run_streaming.await_count == 0


def test_agents_returns_initialized_runtime_pools(client):
    http_client, _, _ = client
    token = _login(http_client)

    response = http_client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    agents = {agent["agent_type"]: agent for agent in response.json()["agents"]}

    assert set(agents) == {"sebastian", "code", "life", "stock"}
    assert agents["sebastian"] == {
        "agent_type": "sebastian",
        "workers": [
            {
                "agent_id": "sebastian_01",
                "status": "idle",
                "session_id": None,
            }
        ],
        "queue_depth": 0,
    }
    for agent_type in ("code", "life", "stock"):
        assert agents[agent_type] == {
            "agent_type": agent_type,
            "workers": [
                {
                    "agent_id": f"{agent_type}_01",
                    "status": "idle",
                    "session_id": None,
                },
                {
                    "agent_id": f"{agent_type}_02",
                    "status": "idle",
                    "session_id": None,
                },
                {
                    "agent_id": f"{agent_type}_03",
                    "status": "idle",
                    "session_id": None,
                },
            ],
            "queue_depth": 0,
        }


def test_agents_reflect_runtime_turn_events(client):
    http_client, _, _ = client
    token = _login(http_client)

    import sebastian.gateway.state as state
    from sebastian.protocol.events.types import Event, EventType

    asyncio.run(
        state.event_bus.publish(
            Event(
                type=EventType.TURN_RECEIVED,
                data={"agent_id": "stock_02", "session_id": "session-123"},
            )
        )
    )

    response = http_client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    agents = {agent["agent_type"]: agent for agent in response.json()["agents"]}
    stock_workers = {worker["agent_id"]: worker for worker in agents["stock"]["workers"]}
    assert stock_workers["stock_02"] == {
        "agent_id": "stock_02",
        "status": "busy",
        "session_id": "session-123",
    }

    asyncio.run(
        state.event_bus.publish(
            Event(
                type=EventType.TURN_RESPONSE,
                data={"session_id": "session-123", "content": "done"},
            )
        )
    )

    response = http_client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    agents = {agent["agent_type"]: agent for agent in response.json()["agents"]}
    stock_workers = {worker["agent_id"]: worker for worker in agents["stock"]["workers"]}
    assert stock_workers["stock_02"] == {
        "agent_id": "stock_02",
        "status": "idle",
        "session_id": None,
    }
