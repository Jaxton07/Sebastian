from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sebastian.gateway.auth import require_auth

router = APIRouter(tags=["tasks"])


@router.get("/tasks")
async def list_tasks(
    status: str | None = None,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    async with state.session_factory() as session:
        from sebastian.store.task_store import TaskStore
        store = TaskStore(session)
        tasks = await store.list_tasks(status=status)
    return {"tasks": [t.model_dump(mode="json") for t in tasks]}


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    async with state.session_factory() as session:
        from sebastian.store.task_store import TaskStore
        store = TaskStore(session)
        task = await store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    async with state.session_factory() as session:
        from sebastian.store.task_store import TaskStore
        store = TaskStore(session)
        checkpoints = await store.get_checkpoints(task_id)
    return {
        "task": task.model_dump(mode="json"),
        "checkpoints": [cp.model_dump(mode="json") for cp in checkpoints],
    }


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "paused": cancelled}


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "cancelled": cancelled}
