from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles

from sebastian.core.types import Session

INDEX_FILE = "index.json"
_LOCK = asyncio.Lock()


class IndexStore:
    """Read and write the top-level session listing index."""

    def __init__(self, sessions_dir: Path) -> None:
        self._path = sessions_dir / INDEX_FILE

    async def _read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        async with aiofiles.open(self._path) as file:
            raw = await file.read()
        data = json.loads(raw)
        return data.get("sessions", [])

    async def _write(self, sessions: list[dict[str, Any]]) -> None:
        payload = json.dumps({"version": 1, "sessions": sessions}, default=str)
        async with aiofiles.open(self._path, "w") as file:
            await file.write(payload)

    async def upsert(self, session: Session) -> None:
        async with _LOCK:
            sessions = await self._read()
            entry = {
                "id": session.id,
                "agent": session.agent,
                "title": session.title,
                "status": session.status.value,
                "updated_at": session.updated_at.isoformat(),
                "task_count": session.task_count,
                "active_task_count": session.active_task_count,
            }
            sessions = [existing for existing in sessions if existing["id"] != session.id]
            sessions.insert(0, entry)
            await self._write(sessions)

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._read()

    async def list_by_agent(self, agent: str) -> list[dict[str, Any]]:
        return [session for session in await self._read() if session["agent"] == agent]

    async def remove(self, session_id: str) -> None:
        async with _LOCK:
            sessions = await self._read()
            sessions = [session for session in sessions if session["id"] != session_id]
            await self._write(sessions)
