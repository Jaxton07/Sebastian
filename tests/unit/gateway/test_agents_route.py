from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _build_app_with_mocks(agents: dict, bindings: list) -> FastAPI:
    import sebastian.gateway.state as state

    state.agent_registry = agents
    state.index_store = MagicMock()
    state.index_store.list_by_agent_type = AsyncMock(return_value=[])
    state.llm_registry = MagicMock()
    state.llm_registry.list_bindings = AsyncMock(return_value=bindings)

    app = FastAPI()
    from sebastian.gateway.routes import agents as agents_mod
    from sebastian.gateway.auth import require_auth

    async def _fake_auth() -> dict[str, str]:
        return {"user_id": "test"}

    app.dependency_overrides[require_auth] = _fake_auth
    app.include_router(agents_mod.router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_list_agents_includes_bound_provider_id_when_bound() -> None:
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
        AgentLLMBindingRecord(agent_type="forge", provider_id="prov-123"),
    ]
    app = _build_app_with_mocks(agents, bindings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agents"][0]["agent_type"] == "forge"
    assert data["agents"][0]["bound_provider_id"] == "prov-123"


@pytest.mark.asyncio
async def test_list_agents_returns_null_bound_provider_when_unbound() -> None:
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
    assert data["agents"][0]["bound_provider_id"] is None
