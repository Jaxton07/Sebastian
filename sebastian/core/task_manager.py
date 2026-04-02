from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from sebastian.core.types import Task, TaskStatus
from sebastian.protocol.events.bus import EventBus
from sebastian.protocol.events.types import Event, EventType
from sebastian.store.session_store import SessionStore

logger = logging.getLogger(__name__)

TaskFn = Callable[[Task], Awaitable[None]]


class TaskManager:
    """Submits tasks for async background execution. Persists to SessionStore."""

    def __init__(self, session_store: SessionStore, event_bus: EventBus) -> None:
        self._store = session_store
        self._bus = event_bus
        self._running: dict[str, asyncio.Task] = {}

    async def submit(self, task: Task, fn: TaskFn) -> None:
        await self._store.create_task(task)
        await self._bus.publish(
            Event(
                type=EventType.TASK_CREATED,
                data={
                    "task_id": task.id,
                    "session_id": task.session_id,
                    "goal": task.goal,
                    "assigned_agent": task.assigned_agent,
                },
            )
        )

        async def _run() -> None:
            await self._store.update_task_status(
                task.session_id,
                task.id,
                TaskStatus.RUNNING,
                task.assigned_agent,
            )
            await self._bus.publish(
                Event(type=EventType.TASK_STARTED, data={"task_id": task.id})
            )
            try:
                await fn(task)
                await self._store.update_task_status(
                    task.session_id,
                    task.id,
                    TaskStatus.COMPLETED,
                    task.assigned_agent,
                )
                await self._bus.publish(
                    Event(type=EventType.TASK_COMPLETED, data={"task_id": task.id})
                )
            except asyncio.CancelledError:
                await self._store.update_task_status(
                    task.session_id,
                    task.id,
                    TaskStatus.CANCELLED,
                    task.assigned_agent,
                )
                await self._bus.publish(
                    Event(type=EventType.TASK_CANCELLED, data={"task_id": task.id})
                )
            except Exception as exc:
                logger.exception("Task %s failed", task.id)
                await self._store.update_task_status(
                    task.session_id,
                    task.id,
                    TaskStatus.FAILED,
                    task.assigned_agent,
                )
                await self._bus.publish(
                    Event(
                        type=EventType.TASK_FAILED,
                        data={"task_id": task.id, "error": str(exc)},
                    )
                )
            finally:
                self._running.pop(task.id, None)

        self._running[task.id] = asyncio.create_task(_run())

    async def cancel(self, task_id: str) -> bool:
        t = self._running.get(task_id)
        if t is None:
            return False
        t.cancel()
        return True

    def is_running(self, task_id: str) -> bool:
        return task_id in self._running
