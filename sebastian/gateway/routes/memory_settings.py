from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

import sebastian.gateway.state as state
from sebastian.gateway.auth import require_auth
from sebastian.gateway.state import MemoryRuntimeSettings

router = APIRouter(tags=["memory"])

AuthPayload = dict[str, Any]


@router.get("/memory/settings", response_model=MemoryRuntimeSettings)
async def get_memory_settings(
    _auth: AuthPayload = Depends(require_auth),
) -> MemoryRuntimeSettings:
    return state.memory_settings


@router.put("/memory/settings", response_model=MemoryRuntimeSettings)
async def put_memory_settings(
    body: MemoryRuntimeSettings,
    _auth: AuthPayload = Depends(require_auth),
) -> MemoryRuntimeSettings:
    state.memory_settings = body
    return state.memory_settings
