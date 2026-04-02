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
    from sebastian.gateway.auth import hash_password

    password_hash = hash_password("testpass")

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
                return_value="Session reply",
            ) as mock_chat:
                with patch(
                    "sebastian.orchestrator.sebas.Sebastian.intervene",
                    new_callable=AsyncMock,
                    return_value="Intervened reply",
                ) as mock_intervene:
                    from sebastian.gateway.app import create_app
                    from starlette.testclient import TestClient

                    test_app = create_app()
                    with TestClient(test_app, raise_server_exceptions=True) as test_client:
                        yield test_client, mock_chat, mock_intervene


def _login(client) -> str:
    response = client.post("/api/v1/auth/login", json={"password": "testpass"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_list_sessions_empty(client):
    http_client, _, _ = client
    token = _login(http_client)

    response = http_client.get(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"sessions": []}


def test_get_session_returns_meta_and_messages(client):
    http_client, _, _ = client
    token = _login(http_client)

    import sebastian.gateway.state as state
    from sebastian.core.types import Session

    session = Session(agent="sebastian", title="Hello world")
    assert state.session_store is not None
    assert state.index_store is not None
    import asyncio

    asyncio.run(state.session_store.create_session(session))
    asyncio.run(state.session_store.append_message(session.id, "user", "Hello"))
    asyncio.run(state.index_store.upsert(session))

    response = http_client.get(
        f"/api/v1/sessions/{session.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session"]["id"] == session.id
    assert data["messages"][0]["content"] == "Hello"


def test_send_turn_to_subagent_session_uses_intervention(client):
    http_client, _, mock_intervene = client
    token = _login(http_client)

    import sebastian.gateway.state as state
    from sebastian.core.types import Session
    import asyncio

    session = Session(agent="stock", title="Stock session")
    asyncio.run(state.session_store.create_session(session))
    asyncio.run(state.index_store.upsert(session))

    response = http_client.post(
        f"/api/v1/sessions/{session.id}/turns?agent=stock",
        json={"content": "Please revise the plan"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["response"] == "Intervened reply"
    mock_intervene.assert_awaited_once_with(
        "stock", session.id, "Please revise the plan"
    )


def test_intervene_endpoint_exists_for_subagent_sessions(client):
    http_client, _, mock_intervene = client
    token = _login(http_client)

    import asyncio

    import sebastian.gateway.state as state
    from sebastian.core.types import Session

    session = Session(agent="stock", title="Review this")
    asyncio.run(state.session_store.create_session(session))
    asyncio.run(state.index_store.upsert(session))

    response = http_client.post(
        f"/api/v1/sessions/{session.id}/intervene?agent=stock",
        json={"content": "correct this"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["response"] == "Intervened reply"
    mock_intervene.assert_awaited_with("stock", session.id, "correct this")
