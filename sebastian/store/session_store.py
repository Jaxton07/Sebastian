from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles

from sebastian.core.types import (
    Checkpoint,
    ResourceBudget,
    Session,
    Task,
    TaskPlan,
    TaskStatus,
)

_SESSION_LOCKS_BY_PATH: dict[Path, asyncio.Lock] = {}


def _session_dir(sessions_dir: Path, session: Session) -> Path:
    """Return the session directory, creating the required structure."""
    if session.agent == "sebastian":
        directory = sessions_dir / "sebastian" / session.id
    else:
        directory = sessions_dir / "subagents" / session.agent / session.id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "tasks").mkdir(exist_ok=True)
    return directory


def _session_dir_by_id(sessions_dir: Path, session_id: str, agent: str) -> Path:
    if agent == "sebastian":
        return sessions_dir / "sebastian" / session_id
    return sessions_dir / "subagents" / agent / session_id


class SessionStore:
    """File-based storage for sessions, messages, tasks, and checkpoints."""

    def __init__(self, sessions_dir: Path) -> None:
        self._dir = sessions_dir

    async def create_session(self, session: Session) -> Session:
        directory = _session_dir(self._dir, session)
        async with self._session_lock(session.id, session.agent):
            await self._write_session_meta(session)
        return session

    async def get_session(
        self, session_id: str, agent: str = "sebastian"
    ) -> Session | None:
        directory = _session_dir_by_id(self._dir, session_id, agent)
        meta_path = directory / "meta.json"
        if not meta_path.exists():
            return None
        async with aiofiles.open(meta_path) as file:
            raw = await file.read()
        return Session(**json.loads(raw))

    async def update_session(self, session: Session) -> None:
        async with self._session_lock(session.id, session.agent):
            await self._write_session_meta(session)

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: str = "sebastian",
    ) -> None:
        directory = _session_dir_by_id(self._dir, session_id, agent)
        message = json.dumps(
            {
                "role": role,
                "content": content,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        async with aiofiles.open(directory / "messages.jsonl", "a") as file:
            await file.write(message + "\n")

    async def get_messages(
        self, session_id: str, agent: str = "sebastian", limit: int = 50
    ) -> list[dict[str, Any]]:
        directory = _session_dir_by_id(self._dir, session_id, agent)
        path = directory / "messages.jsonl"
        if not path.exists():
            return []
        async with aiofiles.open(path) as file:
            lines = await file.readlines()
        messages = [json.loads(line) for line in lines if line.strip()]
        return messages[-limit:]

    async def create_task(self, task: Task) -> Task:
        async with self._session_lock(task.session_id, task.assigned_agent):
            directory = _session_dir_by_id(self._dir, task.session_id, task.assigned_agent)
            tasks_dir = directory / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)
            await self._atomic_write_text(
                tasks_dir / f"{task.id}.json",
                task.model_dump_json(),
            )
            await self._refresh_session_counts_locked(task.session_id, task.assigned_agent)
        return task

    async def get_task(
        self, session_id: str, task_id: str, agent: str = "sebastian"
    ) -> Task | None:
        directory = _session_dir_by_id(self._dir, session_id, agent)
        path = directory / "tasks" / f"{task_id}.json"
        if not path.exists():
            return None
        async with aiofiles.open(path) as file:
            raw = await file.read()
        return _task_from_dict(json.loads(raw))

    async def list_tasks(
        self, session_id: str, agent: str = "sebastian"
    ) -> list[Task]:
        directory = _session_dir_by_id(self._dir, session_id, agent)
        tasks_dir = directory / "tasks"
        if not tasks_dir.exists():
            return []
        tasks: list[Task] = []
        for path in sorted(tasks_dir.glob("*.json")):
            async with aiofiles.open(path) as file:
                raw = await file.read()
            tasks.append(_task_from_dict(json.loads(raw)))
        return tasks

    async def update_task_status(
        self,
        session_id: str,
        task_id: str,
        status: TaskStatus,
        agent: str = "sebastian",
    ) -> None:
        async with self._session_lock(session_id, agent):
            task = await self.get_task(session_id, task_id, agent)
            if task is None:
                return
            task.status = status
            task.updated_at = datetime.now(timezone.utc)
            if status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                task.completed_at = datetime.now(timezone.utc)
            directory = _session_dir_by_id(self._dir, session_id, agent)
            await self._atomic_write_text(
                directory / "tasks" / f"{task_id}.json",
                task.model_dump_json(),
            )
            await self._refresh_session_counts_locked(session_id, agent)

    async def append_checkpoint(
        self,
        session_id: str,
        checkpoint: Checkpoint,
        agent: str = "sebastian",
    ) -> None:
        directory = _session_dir_by_id(self._dir, session_id, agent)
        path = directory / "tasks" / f"{checkpoint.task_id}.jsonl"
        line = json.dumps(checkpoint.model_dump(mode="json"))
        async with aiofiles.open(path, "a") as file:
            await file.write(line + "\n")

    async def get_checkpoints(
        self, session_id: str, task_id: str, agent: str = "sebastian"
    ) -> list[Checkpoint]:
        directory = _session_dir_by_id(self._dir, session_id, agent)
        path = directory / "tasks" / f"{task_id}.jsonl"
        if not path.exists():
            return []
        async with aiofiles.open(path) as file:
            lines = await file.readlines()
        return [Checkpoint(**json.loads(line)) for line in lines if line.strip()]

    async def _atomic_write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        async with aiofiles.open(temp_path, "w") as file:
            await file.write(content)
        os.replace(temp_path, path)

    def _session_lock(self, session_id: str, agent: str) -> asyncio.Lock:
        meta_path = (_session_dir_by_id(self._dir, session_id, agent) / "meta.json").resolve()
        return _SESSION_LOCKS_BY_PATH.setdefault(meta_path, asyncio.Lock())

    async def _write_session_meta(self, session: Session) -> None:
        directory = _session_dir_by_id(self._dir, session.id, session.agent)
        await self._atomic_write_text(directory / "meta.json", session.model_dump_json())

    async def _refresh_session_counts_locked(self, session_id: str, agent: str) -> None:
        session = await self.get_session(session_id, agent)
        if session is None:
            return
        tasks = await self.list_tasks(session_id, agent)
        terminal_statuses = {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
        session.task_count = len(tasks)
        session.active_task_count = sum(
            1 for task in tasks if task.status not in terminal_statuses
        )
        session.updated_at = datetime.now(timezone.utc)
        await self._write_session_meta(session)


def _task_from_dict(data: dict[str, Any]) -> Task:
    return Task(
        id=data["id"],
        session_id=data["session_id"],
        goal=data["goal"],
        status=TaskStatus(data["status"]),
        assigned_agent=data.get("assigned_agent", "sebastian"),
        parent_task_id=data.get("parent_task_id"),
        plan=TaskPlan(**data["plan"]) if data.get("plan") else None,
        resource_budget=ResourceBudget(**data.get("resource_budget", {})),
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
        completed_at=(
            datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None
        ),
    )
