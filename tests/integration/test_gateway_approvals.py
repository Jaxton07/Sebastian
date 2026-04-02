from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("SEBASTIAN_JWT_SECRET", "test-secret-key")
os.environ.setdefault("SEBASTIAN_DATA_DIR", "/tmp/sebastian_test")


@pytest.fixture
def client(tmp_path):
    from sebastian.gateway.auth import hash_password

    password_hash = hash_password("testpass")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("SEBASTIAN_OWNER_PASSWORD_HASH", password_hash)
        monkeypatch.setenv("SEBASTIAN_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
        monkeypatch.setenv("SEBASTIAN_JWT_SECRET", "test-secret-key")

        import sebastian.config as cfg_module

        importlib.reload(cfg_module)
        monkeypatch.setattr(
            cfg_module.settings,
            "sebastian_owner_password_hash",
            password_hash,
        )

        from sebastian.gateway.app import create_app
        from starlette.testclient import TestClient

        app = create_app()
        with TestClient(app, raise_server_exceptions=True) as test_client:
            yield test_client


def _login(client) -> str:
    response = client.post("/api/v1/auth/login", json={"password": "testpass"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_list_approvals_uses_db_factory_and_returns_description(client) -> None:
    import asyncio

    import sebastian.gateway.state as state
    from sebastian.store.models import ApprovalRecord

    async def seed() -> None:
        async with state.db_factory() as session:
            session.add(
                ApprovalRecord(
                    id="approval-1",
                    task_id="task-1",
                    session_id="session-1",
                    tool_name="shell",
                    tool_input={"cmd": "ls"},
                    status="pending",
                    created_at=datetime.now(timezone.utc),
                    resolved_at=None,
                )
            )
            await session.commit()

    asyncio.run(seed())

    token = _login(client)
    response = client.get(
        "/api/v1/approvals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    approval = response.json()["approvals"][0]
    assert approval["id"] == "approval-1"
    assert approval["description"]

