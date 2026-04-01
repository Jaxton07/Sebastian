from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sebastian.gateway.auth import require_auth

router = APIRouter(tags=["approvals"])


@router.get("/approvals")
async def list_approvals(_auth: dict = Depends(require_auth)) -> dict:
    import sebastian.gateway.state as state
    from sqlalchemy import select
    from sebastian.store.models import ApprovalRecord
    async with state.session_factory() as session:
        result = await session.execute(
            select(ApprovalRecord).where(ApprovalRecord.status == "pending")
        )
        records = result.scalars().all()
    return {
        "approvals": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "tool_name": r.tool_name,
                "tool_input": r.tool_input,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
    }


@router.post("/approvals/{approval_id}/grant")
async def grant_approval(
    approval_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    await _resolve(approval_id, granted=True, state=state)
    return {"approval_id": approval_id, "granted": True}


@router.post("/approvals/{approval_id}/deny")
async def deny_approval(
    approval_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    await _resolve(approval_id, granted=False, state=state)
    return {"approval_id": approval_id, "granted": False}


async def _resolve(approval_id: str, granted: bool, state) -> None:
    from sqlalchemy import select
    from sebastian.store.models import ApprovalRecord
    async with state.session_factory() as session:
        result = await session.execute(
            select(ApprovalRecord).where(ApprovalRecord.id == approval_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        record.status = "granted" if granted else "denied"
        record.resolved_at = datetime.now(timezone.utc)
        await session.commit()
    await state.conversation.resolve_approval(approval_id, granted)
