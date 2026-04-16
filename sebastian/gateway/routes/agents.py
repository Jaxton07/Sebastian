from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from sebastian.gateway.auth import require_auth

router = APIRouter(tags=["agents"])

AuthPayload = dict[str, Any]
JSONDict = dict[str, Any]


class BindingUpdate(BaseModel):
    provider_id: str | None = None


@router.get("/agents")
async def list_agents(_auth: AuthPayload = Depends(require_auth)) -> JSONDict:
    import sebastian.gateway.state as state

    bindings = await state.llm_registry.list_bindings()
    binding_map = {b.agent_type: b.provider_id for b in bindings}

    agents = []
    for agent_type, config in state.agent_registry.items():
        if agent_type == "sebastian":
            continue

        sessions = await state.index_store.list_by_agent_type(agent_type)
        active_count = sum(1 for s in sessions if s.get("status") == "active")

        agents.append(
            {
                "agent_type": agent_type,
                "description": config.description,
                "active_session_count": active_count,
                "max_children": config.max_children,
                "bound_provider_id": binding_map.get(agent_type),
            }
        )

    return {"agents": agents}


@router.put("/agents/{agent_type}/llm-binding")
async def set_agent_binding(
    agent_type: str,
    body: BindingUpdate,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    if agent_type == "sebastian" or agent_type not in state.agent_registry:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.provider_id is not None:
        record = await state.llm_registry._get_record(body.provider_id)
        if record is None:
            raise HTTPException(status_code=400, detail="Provider not found")

    binding = await state.llm_registry.set_binding(agent_type, body.provider_id)
    return {"agent_type": binding.agent_type, "provider_id": binding.provider_id}


@router.delete("/agents/{agent_type}/llm-binding", status_code=204)
async def clear_agent_binding(
    agent_type: str,
    _auth: AuthPayload = Depends(require_auth),
) -> Response:
    import sebastian.gateway.state as state

    if agent_type == "sebastian" or agent_type not in state.agent_registry:
        raise HTTPException(status_code=404, detail="Agent not found")

    await state.llm_registry.clear_binding(agent_type)
    return Response(status_code=204)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
