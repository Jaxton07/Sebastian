from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from sebastian.memory.episode_store import ensure_episode_fts
from sebastian.memory.slots import DEFAULT_SLOT_REGISTRY
from sebastian.store.models import MemorySlotRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


async def init_memory_storage(engine: AsyncEngine) -> None:
    """Initialize memory storage virtual tables. Idempotent. Call after init_db()."""
    async with engine.begin() as conn:
        await ensure_episode_fts(conn)


async def seed_builtin_slots(session: AsyncSession) -> None:
    """Insert MemorySlotRecord rows for every built-in slot; idempotent."""
    existing_rows = await session.execute(select(MemorySlotRecord.slot_id))
    existing = {row[0] for row in existing_rows.all()}
    now = datetime.now(UTC)
    for slot in DEFAULT_SLOT_REGISTRY.list_all():
        if slot.slot_id in existing:
            continue
        session.add(
            MemorySlotRecord(
                slot_id=slot.slot_id,
                scope=slot.scope.value,
                subject_kind=slot.subject_kind,
                cardinality=slot.cardinality.value,
                resolution_policy=slot.resolution_policy.value,
                kind_constraints=[k.value for k in slot.kind_constraints],
                description=slot.description,
                is_builtin=True,
                created_at=now,
                updated_at=now,
            )
        )
    await session.commit()
