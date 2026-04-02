from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sebastian.gateway.auth import require_auth

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
async def list_sessions(_auth: dict = Depends(require_auth)) -> dict:
    import sebastian.gateway.state as state

    sessions = await state.index_store.list_all()
    return {"sessions": sessions}


@router.get("/agents/{agent}/sessions")
async def list_agent_sessions(agent: str, _auth: dict = Depends(require_auth)) -> dict:
    import sebastian.gateway.state as state

    sessions = await state.index_store.list_by_agent(agent)
    return {"agent": agent, "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    agent: str = "sebastian",
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state

    session = await state.session_store.get_session(session_id, agent)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await state.session_store.get_messages(session_id, agent, limit=50)
    return {"session": session.model_dump(mode="json"), "messages": messages}


class SendTurnBody(BaseModel):
    content: str


@router.post("/sessions/{session_id}/turns")
async def send_turn_to_session(
    session_id: str,
    body: SendTurnBody,
    agent: str = "sebastian",
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state

    session = await state.session_store.get_session(session_id, agent)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if agent == "sebastian":
        response = await state.sebastian.chat(body.content, session_id)
    else:
        response = await state.sebastian.intervene(agent, session_id, body.content)

    session.updated_at = datetime.now(timezone.utc)
    await state.session_store.update_session(session)
    await state.index_store.upsert(session)

    return {
        "session_id": session_id,
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/sessions/{session_id}/intervene")
async def intervene_session(
    session_id: str,
    body: SendTurnBody,
    agent: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state

    session = await state.session_store.get_session(session_id, agent)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    response = await state.sebastian.intervene(agent, session_id, body.content)
    session.updated_at = datetime.now(timezone.utc)
    await state.session_store.update_session(session)
    await state.index_store.upsert(session)
    return {
        "session_id": session_id,
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/sessions/{session_id}/tasks")
async def list_session_tasks(
    session_id: str,
    agent: str = "sebastian",
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state

    tasks = await state.session_store.list_tasks(session_id, agent)
    return {"tasks": [task.model_dump(mode="json") for task in tasks]}


@router.post("/sessions/{session_id}/tasks/{task_id}/pause")
async def pause_task(
    session_id: str,
    task_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state

    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "paused": cancelled}


@router.delete("/sessions/{session_id}/tasks/{task_id}")
async def cancel_task(
    session_id: str,
    task_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state

    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "cancelled": cancelled}
