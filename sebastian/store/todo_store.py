# mypy: disable-error-code=import-untyped

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles

from sebastian.core.types import TodoItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from sebastian.store.session_todos import SessionTodoStore


class TodoStore:
    """per-session todo 存储。

    当 db_factory 非 None 时写 SQLite session_todos 表；否则退回文件路径（向后兼容）。
    """

    def __init__(
        self,
        sessions_dir: Path | None = None,
        db_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._dir = sessions_dir
        self._db_todo: SessionTodoStore | None = None
        if db_factory is not None:
            from sebastian.store.session_todos import SessionTodoStore as _SessionTodoStore

            self._db_todo = _SessionTodoStore(db_factory)

    def _todos_path(self, agent_type: str, session_id: str) -> Path:
        assert self._dir is not None, "sessions_dir required for file-backed TodoStore"
        return self._dir / agent_type / session_id / "todos.json"

    async def read(self, agent_type: str, session_id: str) -> list[TodoItem]:
        if self._db_todo is not None:
            return await self._db_todo.read(agent_type, session_id)
        path = self._todos_path(agent_type, session_id)
        if not path.exists():
            return []
        async with aiofiles.open(path) as f:
            raw = await f.read()
        data = json.loads(raw)
        return [TodoItem(**item) for item in data.get("todos", [])]

    async def write(
        self,
        agent_type: str,
        session_id: str,
        todos: list[TodoItem],
    ) -> None:
        if self._db_todo is not None:
            await self._db_todo.write(agent_type, session_id, todos)
            return
        path = self._todos_path(agent_type, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "todos": [item.model_dump(mode="json", by_alias=True) for item in todos],
            "updated_at": datetime.now(UTC).isoformat(),
        }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)

        tmp_path = path.with_suffix(".json.tmp")
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            await f.write(serialized)
        os.replace(tmp_path, path)
