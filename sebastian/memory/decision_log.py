from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from sebastian.memory.types import ResolveDecision
from sebastian.store.models import MemoryDecisionLogRecord


class MemoryDecisionLogger:
    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def append(
        self,
        decision: ResolveDecision,
        *,
        worker: str,
        model: str | None,
        rule_version: str,
    ) -> MemoryDecisionLogRecord:
        record = MemoryDecisionLogRecord(
            id=str(uuid4()),
            decision=decision.decision.value,
            subject_id=decision.subject_id,
            scope=decision.scope.value,
            slot_id=decision.slot_id,
            candidate=decision.candidate.model_dump(mode="json"),
            conflicts=[],
            reason=decision.reason,
            old_memory_ids=list(decision.old_memory_ids),
            new_memory_id=decision.new_memory.id if decision.new_memory is not None else None,
            worker=worker,
            model=model,
            rule_version=rule_version,
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        await self._session.flush()
        return record
