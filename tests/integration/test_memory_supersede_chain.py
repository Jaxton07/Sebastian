"""Integration test: SUPERSEDE 全链路.

Drives a full SUPERSEDE flow through the public ``memory_save`` and
``memory_search`` tool entrypoints plus the underlying profile/decision
stores. The scenario:

1. Seed one ACTIVE ``ProfileMemoryRecord`` in a SINGLE/SUPERSEDE slot.
2. Call ``memory_save`` with a conflicting value for the same slot.
3. Verify old row SUPERSEDED, new row ACTIVE, decision log entry created.
4. Call ``memory_search`` and verify only the new (active) record surfaces.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import sqlalchemy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import sebastian.gateway.state as state_module
from sebastian.capabilities.tools.memory_save import memory_save
from sebastian.capabilities.tools.memory_search import memory_search
from sebastian.memory.types import (
    MemoryDecisionType,
    MemoryKind,
    MemoryScope,
    MemorySource,
    MemoryStatus,
)
from sebastian.store import models  # noqa: F401 — registers ORM models
from sebastian.store.database import Base
from sebastian.store.models import MemoryDecisionLogRecord, ProfileMemoryRecord

# SINGLE/SUPERSEDE slot with FACT kind constraint (see sebastian/memory/slots.py).
_SLOT_ID = "user.current_project_focus"


async def _create_in_memory_factory() -> async_sessionmaker:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # EpisodeMemoryStore.search requires the FTS5 virtual table.
        await conn.execute(
            sqlalchemy.text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS episode_memories_fts "
                "USING fts5(memory_id UNINDEXED, content_segmented, tokenize=unicode61)"
            )
        )
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def enabled_memory_state(monkeypatch):
    """Patch ``gateway.state`` with memory enabled and a real in-memory DB."""
    fake_settings = MagicMock()
    fake_settings.enabled = True
    monkeypatch.setattr(state_module, "memory_settings", fake_settings, raising=False)

    factory = await _create_in_memory_factory()
    monkeypatch.setattr(state_module, "db_factory", factory, raising=False)
    return factory


@pytest.mark.asyncio
async def test_supersede_chain_from_memory_save_to_search(enabled_memory_state) -> None:
    """Full SUPERSEDE flow through public tools + stores.

    Old row gets demoted, new row becomes active, decision log records the
    transition, and ``memory_search`` filters out the superseded row.
    """
    factory = enabled_memory_state
    now = datetime.now(UTC)
    old_id = "pm-old"
    old_content = "旧项目 Alpha"
    new_content = "新项目 Beta"

    # --- Step 1: seed one ACTIVE profile record in the target slot ---------
    async with factory() as session:
        session.add(
            ProfileMemoryRecord(
                id=old_id,
                subject_id="owner",
                scope=MemoryScope.USER.value,
                slot_id=_SLOT_ID,
                kind=MemoryKind.FACT.value,
                content=old_content,
                structured_payload={},
                source=MemorySource.EXPLICIT.value,
                confidence=1.0,
                status=MemoryStatus.ACTIVE.value,
                valid_from=None,
                valid_until=None,
                provenance={},
                policy_tags=[],
                created_at=now,
                updated_at=now,
                last_accessed_at=None,
                access_count=0,
            )
        )
        await session.commit()

    # --- Step 2: memory_save a new value for the same SINGLE slot ----------
    save_result = await memory_save(
        content=new_content,
        slot_id=_SLOT_ID,
        scope="user",
    )
    assert save_result.ok is True, f"memory_save failed: {save_result.error}"

    # --- Step 3: assert SUPERSEDE bookkeeping ------------------------------
    async with factory() as session:
        rows = (
            await session.scalars(
                select(ProfileMemoryRecord).where(
                    ProfileMemoryRecord.slot_id == _SLOT_ID
                )
            )
        ).all()
        assert len(rows) == 2, f"expected old+new rows, got {[r.content for r in rows]}"

        by_status = {r.status: r for r in rows}
        assert MemoryStatus.SUPERSEDED.value in by_status
        assert MemoryStatus.ACTIVE.value in by_status

        old_row = by_status[MemoryStatus.SUPERSEDED.value]
        new_row = by_status[MemoryStatus.ACTIVE.value]
        assert old_row.id == old_id
        assert old_row.content == old_content
        assert new_row.content == new_content

        logs = (
            await session.scalars(
                select(MemoryDecisionLogRecord).where(
                    MemoryDecisionLogRecord.decision
                    == MemoryDecisionType.SUPERSEDE.value
                )
            )
        ).all()
        assert len(logs) == 1, f"expected 1 SUPERSEDE log, got {len(logs)}"
        log = logs[0]
        assert log.old_memory_ids == [old_id]
        assert log.new_memory_id == new_row.id
        assert log.slot_id == _SLOT_ID

    # --- Step 4: memory_search must return the new row only ----------------
    # "项目" matches content; profile lane is always on for non-small-talk
    # queries, so the superseded row would surface here if search_active
    # failed to filter by status.
    search_result = await memory_search(query="项目", limit=5)
    assert search_result.ok is True
    assert isinstance(search_result.output, dict)

    items = search_result.output["items"]
    contents = [item["content"] for item in items]
    assert new_content in contents
    assert old_content not in contents
