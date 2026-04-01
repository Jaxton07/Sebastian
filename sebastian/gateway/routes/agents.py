from __future__ import annotations
from fastapi import APIRouter, Depends
from sebastian.gateway.auth import require_auth

router = APIRouter(tags=["agents"])


@router.get("/agents")
async def list_agents(_auth: dict = Depends(require_auth)) -> dict:
    import sebastian.gateway.state as state
    return {
        "agents": [
            {
                "name": state.sebastian.name,
                "status": "running",
                "running_tasks": len(state.sebastian._task_manager._running),
            }
        ]
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
