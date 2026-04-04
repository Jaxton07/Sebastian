from __future__ import annotations

import asyncio
from collections import deque
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sebastian.protocol.a2a.dispatcher import A2ADispatcher


class WorkerStatus(StrEnum):
    """Lifecycle state for a worker slot."""

    IDLE = "idle"
    BUSY = "busy"


class AgentPool:
    """Fixed-size worker slot pool for a given agent type."""

    def __init__(self, agent_type: str, worker_count: int = 3) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be at least 1")

        self._agent_type = agent_type
        self._workers: dict[str, WorkerStatus] = {
            f"{agent_type}_{index:02d}": WorkerStatus.IDLE for index in range(1, worker_count + 1)
        }
        self._waiters: deque[asyncio.Future[str]] = deque()
        self._current_goals: dict[str, str | None] = {
            worker_id: None for worker_id in self._workers
        }
        self._worker_tasks: list[asyncio.Task[None]] = []

    async def acquire(self) -> str:
        """Return an idle worker_id or wait until one becomes available."""
        for worker_id, status in self._workers.items():
            if status == WorkerStatus.IDLE:
                self._workers[worker_id] = WorkerStatus.BUSY
                return worker_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._waiters.append(future)

        try:
            return await future
        except asyncio.CancelledError:
            # Remove this future from the waiters deque so it does not grow
            # unboundedly when many callers cancel their acquire() (m1).
            try:
                self._waiters.remove(future)
            except ValueError:
                pass  # Already removed by release().
            raise

    def release(self, worker_id: str) -> None:
        """Return a worker to the next waiter or mark it idle."""
        self._require_busy(worker_id)

        while self._waiters:
            waiter = self._waiters.popleft()
            if waiter.done():
                continue
            self._workers[worker_id] = WorkerStatus.BUSY
            waiter.set_result(worker_id)
            break
        else:
            self._workers[worker_id] = WorkerStatus.IDLE

    def mark_busy(self, worker_id: str) -> None:
        """Mark a specific worker busy without assigning it through queueing."""
        self._require_known_worker(worker_id)
        if self._workers[worker_id] == WorkerStatus.BUSY:
            raise ValueError(f"Worker {worker_id} is already busy")
        self._workers[worker_id] = WorkerStatus.BUSY

    def mark_idle(self, worker_id: str) -> None:
        """Mark a specific worker idle without releasing queued waiters."""
        self._require_busy(worker_id)
        self._workers[worker_id] = WorkerStatus.IDLE

    def status(self) -> dict[str, WorkerStatus]:
        """Return a snapshot of all worker statuses."""
        return dict(self._workers)

    @property
    def queue_depth(self) -> int:
        """Return the number of queued waiters."""
        return sum(1 for waiter in self._waiters if not waiter.done())

    @property
    def current_goals(self) -> dict[str, str | None]:
        """Return a snapshot of current goals per worker."""
        return dict(self._current_goals)

    def start_worker_loops(
        self,
        queue: asyncio.Queue[Any],
        dispatcher: A2ADispatcher,
        agent_instances: dict[str, Any],
    ) -> list[asyncio.Task[None]]:
        """Start one worker coroutine per agent instance. Returns the tasks."""
        tasks: list[asyncio.Task[None]] = []
        for worker_id, agent in agent_instances.items():
            task = asyncio.create_task(
                self._worker_loop(worker_id, queue, dispatcher, agent),
                name=f"a2a_worker_{worker_id}",
            )
            tasks.append(task)
        self._worker_tasks = tasks
        return tasks

    async def _worker_loop(
        self,
        worker_id: str,
        queue: asyncio.Queue[Any],
        dispatcher: A2ADispatcher,
        agent: Any,
    ) -> None:
        """Run until cancelled, pulling tasks from queue and delegating to agent."""
        from sebastian.protocol.a2a.types import TaskResult

        while True:
            task = await queue.get()
            self._current_goals[worker_id] = task.goal
            try:
                result = await agent.execute_delegated_task(task)
                dispatcher.resolve(result)
            except asyncio.CancelledError:
                dispatcher.resolve(
                    TaskResult(task_id=task.task_id, ok=False, error="Worker cancelled")
                )
                raise
            except Exception as exc:
                dispatcher.resolve(
                    TaskResult(task_id=task.task_id, ok=False, error=str(exc))
                )
            finally:
                self._current_goals[worker_id] = None
                queue.task_done()

    def _require_known_worker(self, worker_id: str) -> None:
        if worker_id not in self._workers:
            raise KeyError(worker_id)

    def _require_busy(self, worker_id: str) -> None:
        self._require_known_worker(worker_id)
        if self._workers[worker_id] != WorkerStatus.BUSY:
            raise ValueError(f"Worker {worker_id} is not busy")
