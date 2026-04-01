from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sebastian.store.models import TurnRecord


@dataclass
class TurnEntry:
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


class EpisodicMemory:
    """Persistent conversation history backed by SQLite.
    Each conversation turn (user + assistant) is stored as a TurnRecord."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_turn(self, session_id: str, role: str, content: str) -> TurnEntry:
        entry = TurnRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(entry)
        await self._session.commit()
        return TurnEntry(
            id=entry.id,
            session_id=entry.session_id,
            role=entry.role,
            content=entry.content,
            created_at=entry.created_at,
        )

    async def get_turns(self, session_id: str, limit: int = 50) -> list[TurnEntry]:
        result = await self._session.execute(
            select(TurnRecord)
            .where(TurnRecord.session_id == session_id)
            .order_by(TurnRecord.created_at.desc())
            .limit(limit)
        )
        records = list(reversed(result.scalars().all()))
        return [
            TurnEntry(r.id, r.session_id, r.role, r.content, r.created_at)
            for r in records
        ]
