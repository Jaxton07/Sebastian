from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sebastian.protocol.a2a.types import TaskResult


@pytest.mark.asyncio
async def test_delegate_returns_ok_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_dispatcher = MagicMock()
    mock_dispatcher.delegate = AsyncMock(
        return_value=TaskResult(task_id="t1", ok=True, output={"summary": "done"})
    )

    monkeypatch.setattr(
        "sebastian.orchestrator.tools.delegate._get_dispatcher",
        lambda: mock_dispatcher,
    )

    from sebastian.orchestrator.tools.delegate import delegate_to_agent

    result = await delegate_to_agent("code", "write a hello world", "")
    assert result.ok is True
    assert result.output == "done"


@pytest.mark.asyncio
async def test_delegate_returns_error_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_dispatcher = MagicMock()
    mock_dispatcher.delegate = AsyncMock(
        return_value=TaskResult(task_id="t2", ok=False, error="agent unavailable")
    )

    monkeypatch.setattr(
        "sebastian.orchestrator.tools.delegate._get_dispatcher",
        lambda: mock_dispatcher,
    )

    from sebastian.orchestrator.tools.delegate import delegate_to_agent

    result = await delegate_to_agent("stock", "get AAPL price", "")
    assert result.ok is False
    assert result.error == "agent unavailable"


@pytest.mark.asyncio
async def test_delegate_uses_fallback_summary_when_no_summary_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_dispatcher = MagicMock()
    mock_dispatcher.delegate = AsyncMock(
        return_value=TaskResult(task_id="t3", ok=True, output={"result": "hello"})
    )

    monkeypatch.setattr(
        "sebastian.orchestrator.tools.delegate._get_dispatcher",
        lambda: mock_dispatcher,
    )

    from sebastian.orchestrator.tools.delegate import delegate_to_agent

    result = await delegate_to_agent("code", "run script", "")
    assert result.ok is True
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_delegate_uses_default_error_when_error_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_dispatcher = MagicMock()
    mock_dispatcher.delegate = AsyncMock(
        return_value=TaskResult(task_id="t4", ok=False, error=None)
    )

    monkeypatch.setattr(
        "sebastian.orchestrator.tools.delegate._get_dispatcher",
        lambda: mock_dispatcher,
    )

    from sebastian.orchestrator.tools.delegate import delegate_to_agent

    result = await delegate_to_agent("code", "fail task", "")
    assert result.ok is False
    assert result.error == "Delegation failed"
