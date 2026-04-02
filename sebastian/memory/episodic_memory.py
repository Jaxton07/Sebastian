from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sebastian.store.session_store import SessionStore


@dataclass
class TurnEntry:
    role: str
    content: str
    ts: str


class EpisodicMemory:
    """Conversation history backed by the file-based SessionStore."""

    def __init__(self, session_store: SessionStore) -> None:
        self._store = session_store

    async def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: str = "sebastian",
    ) -> TurnEntry:
        await self._store.append_message(session_id, role, content, agent)
        return TurnEntry(
            role=role,
            content=content,
            ts=datetime.now(timezone.utc).isoformat(),
        )

    async def get_turns(
        self,
        session_id: str,
        agent: str = "sebastian",
        limit: int = 50,
    ) -> list[TurnEntry]:
        messages = await self._store.get_messages(session_id, agent, limit)
        return [
            TurnEntry(role=message["role"], content=message["content"], ts=message.get("ts", ""))
            for message in messages
        ]
