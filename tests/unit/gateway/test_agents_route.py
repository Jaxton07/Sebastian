from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _build_app_with_mocks(
    agents: dict,
    bindings: list,
    accounts: list | None = None,
) -> FastAPI:
    import sebastian.gateway.state as state

    _accounts = accounts or []

    state.agent_registry = agents
    state.session_store = MagicMock()
    state.session_store.list_sessions_by_agent_type = AsyncMock(return_value=[])
    state.llm_registry = MagicMock()
    state.llm_registry.list_bindings = AsyncMock(return_value=bindings)
    state.llm_registry.list_accounts = AsyncMock(return_value=_accounts)
    state.llm_registry.get_binding = AsyncMock(
        side_effect=lambda agent_type: next(
            (b for b in bindings if b.agent_type == agent_type), None
        )
    )
    state.llm_registry.get_account = AsyncMock(
        side_effect=lambda account_id: next((a for a in _accounts if a.id == account_id), None)
    )

    app = FastAPI()
    from sebastian.gateway.auth import require_auth
    from sebastian.gateway.routes import agents as agents_mod

    async def _fake_auth() -> dict[str, str]:
        return {"user_id": "test"}

    app.dependency_overrides[require_auth] = _fake_auth
    app.include_router(agents_mod.router, prefix="/api/v1")
    return app


def _make_account_record(aid: str = "acc-1", provider_type: str = "anthropic") -> MagicMock:
    r = MagicMock()
    r.id = aid
    r.catalog_provider_id = "anthropic"
    r.provider_type = provider_type
    return r


def _make_model_spec(capability: str = "adaptive") -> MagicMock:
    m = MagicMock()
    m.thinking_capability = capability
    return m


@pytest.mark.asyncio
async def test_list_agents_includes_bound_account_id_when_bound() -> None:
    from sebastian.agents._loader import AgentConfig
    from sebastian.store.models import AgentLLMBindingRecord

    agents = {
        "forge": AgentConfig(
            agent_type="forge",
            name="ForgeAgent",
            description="Code writer",
            max_children=5,
            stalled_threshold_minutes=5,
            agent_class=MagicMock(),
        )
    }
    bindings = [
        AgentLLMBindingRecord(
            agent_type="forge", account_id="acc-123", model_id="claude-sonnet-4-6"
        ),
    ]
    app = _build_app_with_mocks(agents, bindings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agents"][0]["agent_type"] == "sebastian"
    forge = next(a for a in data["agents"] if a["agent_type"] == "forge")
    assert forge["binding"]["account_id"] == "acc-123"
    assert forge["binding"]["model_id"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_list_agents_returns_null_binding_when_unbound() -> None:
    from sebastian.agents._loader import AgentConfig

    agents = {
        "aide": AgentConfig(
            agent_type="aide",
            name="AideAgent",
            description="Research",
            max_children=2,
            stalled_threshold_minutes=5,
            agent_class=MagicMock(),
        )
    }
    app = _build_app_with_mocks(agents, [])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
    data = resp.json()
    aide = next(a for a in data["agents"] if a["agent_type"] == "aide")
    assert aide["binding"] is None


@pytest.mark.asyncio
async def test_put_binding_sets_account_and_model() -> None:
    from sebastian.agents._loader import AgentConfig
    from sebastian.store.models import AgentLLMBindingRecord

    agents = {
        "forge": AgentConfig(
            agent_type="forge",
            name="ForgeAgent",
            description="Code writer",
            max_children=5,
            stalled_threshold_minutes=5,
            agent_class=MagicMock(),
        )
    }
    account = _make_account_record("acc-1")
    model_spec = _make_model_spec("adaptive")
    app = _build_app_with_mocks(agents, [], accounts=[account])
    import sebastian.gateway.state as state

    state.llm_registry.get_model_spec = AsyncMock(return_value=model_spec)
    state.llm_registry.set_binding = AsyncMock(
        return_value=AgentLLMBindingRecord(
            agent_type="forge", account_id="acc-1", model_id="claude-sonnet-4-6"
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/v1/agents/forge/llm-binding",
            json={"account_id": "acc-1", "model_id": "claude-sonnet-4-6"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_type"] == "forge"
    assert data["account_id"] == "acc-1"
    assert data["model_id"] == "claude-sonnet-4-6"
    # binding changed → effort forced to None
    state.llm_registry.set_binding.assert_awaited_once_with(
        "forge", "acc-1", "claude-sonnet-4-6", thinking_effort=None
    )


@pytest.mark.asyncio
async def test_put_binding_with_null_clears_binding() -> None:
    from sebastian.agents._loader import AgentConfig

    agents = {
        "forge": AgentConfig(
            agent_type="forge",
            name="ForgeAgent",
            description="",
            max_children=5,
            stalled_threshold_minutes=5,
            agent_class=MagicMock(),
        )
    }
    app = _build_app_with_mocks(agents, [])
    import sebastian.gateway.state as state

    state.llm_registry.clear_binding = AsyncMock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/v1/agents/forge/llm-binding",
            json={"account_id": None, "model_id": None},
        )
    assert resp.status_code == 200
    assert resp.json()["account_id"] is None
    assert resp.json()["model_id"] is None
    state.llm_registry.clear_binding.assert_awaited_once_with("forge")


@pytest.mark.asyncio
async def test_put_binding_404_for_unknown_agent() -> None:
    app = _build_app_with_mocks({}, [])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/v1/agents/ghost/llm-binding",
            json={"account_id": "acc-1", "model_id": "model-1"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_binding_400_for_unknown_account() -> None:
    from sebastian.agents._loader import AgentConfig

    agents = {
        "forge": AgentConfig(
            agent_type="forge",
            name="ForgeAgent",
            description="",
            max_children=5,
            stalled_threshold_minutes=5,
            agent_class=MagicMock(),
        )
    }
    app = _build_app_with_mocks(agents, [], accounts=[])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/v1/agents/forge/llm-binding",
            json={"account_id": "bogus", "model_id": "model-1"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_binding_returns_204() -> None:
    from sebastian.agents._loader import AgentConfig

    agents = {
        "forge": AgentConfig(
            agent_type="forge",
            name="ForgeAgent",
            description="",
            max_children=5,
            stalled_threshold_minutes=5,
            agent_class=MagicMock(),
        )
    }
    app = _build_app_with_mocks(agents, [])
    import sebastian.gateway.state as state

    state.llm_registry.clear_binding = AsyncMock(return_value=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/v1/agents/forge/llm-binding")
    assert resp.status_code == 204
    state.llm_registry.clear_binding.assert_awaited_once_with("forge")


@pytest.mark.asyncio
async def test_delete_binding_404_for_unknown_agent() -> None:
    app = _build_app_with_mocks({}, [])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/v1/agents/ghost/llm-binding")
    assert resp.status_code == 404
