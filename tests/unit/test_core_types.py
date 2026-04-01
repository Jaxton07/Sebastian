from __future__ import annotations

import pytest


def test_task_defaults():
    from sebastian.core.types import Task, TaskStatus

    task = Task(goal="Buy groceries")
    assert task.status == TaskStatus.CREATED
    assert task.assigned_agent == "sebastian"
    assert task.id  # auto-generated UUID
    assert task.plan is None


def test_task_status_values():
    from sebastian.core.types import TaskStatus

    assert TaskStatus.CREATED == "created"
    assert TaskStatus.COMPLETED == "completed"


def test_tool_result_ok():
    from sebastian.core.types import ToolResult

    r = ToolResult(ok=True, output={"stdout": "hello"})
    assert r.ok
    assert r.error is None


def test_tool_result_error():
    from sebastian.core.types import ToolResult

    r = ToolResult(ok=False, error="command not found")
    assert not r.ok
    assert r.error == "command not found"


def test_checkpoint_defaults():
    from sebastian.core.types import Checkpoint

    cp = Checkpoint(task_id="abc", step=1, data={"key": "val"})
    assert cp.id
    assert cp.step == 1
