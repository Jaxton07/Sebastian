from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sebastian.core.types import InvalidTaskTransitionError, Session, Task
from sebastian.gateway.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sessions"])

AuthPayload = dict[str, Any]
JSONDict = dict[str, Any]


@router.get("/sessions")
async def list_sessions(
    agent_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    sessions = await state.index_store.list_all()
    if agent_type is not None:
        sessions = [s for s in sessions if s.get("agent_type") == agent_type]
    if status is not None:
        sessions = [s for s in sessions if s.get("status") == status]
    total = len(sessions)
    sessions = sessions[offset : offset + limit]
    return {"sessions": sessions, "total": total}


@router.get("/agents/{agent_type}/sessions")
async def list_agent_sessions(
    agent_type: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    sessions = await state.index_store.list_by_agent_type(agent_type)
    return {"agent_type": agent_type, "sessions": sessions}


@router.get("/agents/{agent_type}/workers/{agent_id}/sessions")
async def list_worker_sessions(
    agent_type: str,
    agent_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    sessions = await state.index_store.list_by_worker(agent_type, agent_id)
    return {
        "agent_type": agent_type,
        "agent_id": agent_id,
        "sessions": sessions,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    session = await _resolve_session(state, session_id)
    messages = await state.session_store.get_messages(
        session_id,
        session.agent_type,
        session.agent_id,
        limit=50,
    )
    return {"session": session.model_dump(mode="json"), "messages": messages}


class SendTurnBody(BaseModel):
    content: str


def _log_background_turn_failure(task: asyncio.Task[object]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception("Background session turn failed", exc_info=exc)


async def _resolve_session(state: Any, session_id: str) -> Session:
    sessions = await state.index_store.list_all()
    session_meta = next((item for item in sessions if item["id"] == session_id), None)
    if session_meta is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session = await state.session_store.get_session(
        session_id,
        session_meta.get("agent_type", "sebastian"),
        session_meta.get("agent_id", "sebastian_01"),
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return cast(Session, session)


async def _touch_session(state: Any, session: Session) -> datetime:
    now = datetime.now(UTC)
    session.updated_at = now
    await state.session_store.update_session(session)
    await state.index_store.upsert(session)
    return now


async def _resolve_session_task(
    state: Any,
    session_id: str,
    task_id: str,
) -> tuple[Session, Task]:
    session = await _resolve_session(state, session_id)
    task = await state.session_store.get_task(
        session_id,
        task_id,
        session.agent_type,
        session.agent_id,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return session, task


def _schedule_session_turn(state: Any, session: Session, content: str) -> None:
    if session.agent_type == "sebastian":
        task = asyncio.create_task(state.sebastian.run_streaming(content, session.id))
    else:
        task = asyncio.create_task(
            state.sebastian.intervene(session.agent_type, session.id, content)
        )
    task.add_done_callback(_log_background_turn_failure)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    session = await _resolve_session(state, session_id)
    await state.session_store.delete_session(session)
    await state.index_store.remove(session_id)
    return {"session_id": session_id, "deleted": True}


@router.post("/sessions/{session_id}/turns")
async def send_turn_to_session(
    session_id: str,
    body: SendTurnBody,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    session = await _resolve_session(state, session_id)
    now = await _touch_session(state, session)
    _schedule_session_turn(state, session, body.content)

    return {
        "session_id": session_id,
        "ts": now.isoformat(),
    }


@router.post("/sessions/{session_id}/intervene")
async def intervene_session(
    session_id: str,
    body: SendTurnBody,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    session = await _resolve_session(state, session_id)
    now = await _touch_session(state, session)
    _schedule_session_turn(state, session, body.content)
    return {
        "session_id": session_id,
        "ts": now.isoformat(),
    }


@router.get("/sessions/{session_id}/tasks")
async def list_session_tasks(
    session_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    session = await _resolve_session(state, session_id)
    tasks = await state.session_store.list_tasks(
        session_id,
        session.agent_type,
        session.agent_id,
    )
    return {"tasks": [task.model_dump(mode="json") for task in tasks]}


@router.get("/sessions/{session_id}/tasks/{task_id}")
async def get_session_task(
    session_id: str,
    task_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    _, task = await _resolve_session_task(state, session_id, task_id)
    return {"task": task.model_dump(mode="json")}


@router.post("/sessions/{session_id}/tasks/{task_id}/pause")
async def pause_task(
    session_id: str,
    task_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    await _resolve_session_task(state, session_id, task_id)
    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "paused": cancelled}


@router.delete("/sessions/{session_id}/tasks/{task_id}")
async def cancel_task(
    session_id: str,
    task_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict:
    import sebastian.gateway.state as state

    await _resolve_session_task(state, session_id, task_id)
    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "cancelled": cancelled}


@router.post(
    "/sessions/{session_id}/tasks/{task_id}/cancel",
    response_model=None,
)
async def cancel_task_post(
    session_id: str,
    task_id: str,
    _auth: AuthPayload = Depends(require_auth),
) -> JSONDict | JSONResponse:
    """Cancel a task by POST (spec Section 8.2).

    Returns 200 + {"ok": true} on success, 404 if not found,
    409 if the state machine forbids cancellation.
    """
    import sebastian.gateway.state as state

    _, task = await _resolve_session_task(state, session_id, task_id)
    try:
        cancelled = await state.sebastian._task_manager.cancel(task_id)
    except InvalidTaskTransitionError as exc:
        # Placeholder for when TaskManager.cancel() is wired through _transition().
        raise HTTPException(
            status_code=409,
            detail={"detail": str(exc), "code": "INVALID_TASK_TRANSITION"},
        ) from exc
    if not cancelled:
        raise HTTPException(status_code=404, detail="Task not found or not cancellable")
    return {"ok": True}
