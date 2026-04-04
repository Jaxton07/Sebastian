from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_worker_loop_processes_task_and_resolves() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from sebastian.core.agent_pool import AgentPool
    from sebastian.protocol.a2a.dispatcher import A2ADispatcher
    from sebastian.protocol.a2a.types import DelegateTask, TaskResult

    dispatcher = A2ADispatcher()
    queue = dispatcher.register_agent("code")
    pool = AgentPool("code", worker_count=1)

    mock_agent = MagicMock()
    mock_agent.execute_delegated_task = AsyncMock(
        return_value=TaskResult(task_id="t1", ok=True, output={"summary": "done"})
    )

    worker_tasks = pool.start_worker_loops(
        queue=queue,
        dispatcher=dispatcher,
        agent_instances={"code_01": mock_agent},
    )

    task = DelegateTask(task_id="t1", goal="write hello.py")
    future = asyncio.create_task(dispatcher.delegate("code", task))

    result = await asyncio.wait_for(future, timeout=2.0)
    assert result.ok is True
    assert result.output["summary"] == "done"

    for wt in worker_tasks:
        wt.cancel()
        try:
            await wt
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_worker_loop_tracks_current_goal() -> None:
    from unittest.mock import MagicMock

    from sebastian.core.agent_pool import AgentPool
    from sebastian.protocol.a2a.dispatcher import A2ADispatcher
    from sebastian.protocol.a2a.types import DelegateTask, TaskResult

    dispatcher = A2ADispatcher()
    queue = dispatcher.register_agent("code")
    pool = AgentPool("code", worker_count=1)

    # Agent that signals when it starts, then waits
    started = asyncio.Event()
    proceed = asyncio.Event()

    async def slow_execute(task: DelegateTask) -> TaskResult:
        started.set()
        await proceed.wait()
        return TaskResult(task_id=task.task_id, ok=True)

    mock_agent = MagicMock()
    mock_agent.execute_delegated_task = slow_execute

    worker_tasks = pool.start_worker_loops(
        queue=queue,
        dispatcher=dispatcher,
        agent_instances={"code_01": mock_agent},
    )

    task = DelegateTask(task_id="t2", goal="long running goal")
    asyncio.create_task(dispatcher.delegate("code", task))

    await asyncio.wait_for(started.wait(), timeout=1.0)
    assert pool.current_goals.get("code_01") == "long running goal"

    proceed.set()
    await asyncio.sleep(0.05)
    assert pool.current_goals.get("code_01") is None

    for wt in worker_tasks:
        wt.cancel()
        try:
            await wt
        except (asyncio.CancelledError, Exception):
            pass
