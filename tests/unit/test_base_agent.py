from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_base_agent_persists_user_turn_before_inference_failure(tmp_path: Path) -> None:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.core.base_agent import BaseAgent
    from sebastian.core.types import Session
    from sebastian.store.session_store import SessionStore

    class TestAgent(BaseAgent):
        name = "sebastian"

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir)
    await store.create_session(
        Session(id="failure-path", agent="sebastian", title="Failure path")
    )

    mock_client = MagicMock()
    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        agent = TestAgent(CapabilityRegistry(), store)

    agent._loop.run = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError, match="boom"):
        await agent.run("Hello", "failure-path")

    messages = await store.get_messages("failure-path")
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_base_agent_writes_messages_to_overridden_agent_context(tmp_path: Path) -> None:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.core.base_agent import BaseAgent
    from sebastian.core.types import Session
    from sebastian.store.session_store import SessionStore

    class TestAgent(BaseAgent):
        name = "sebastian"

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir)
    await store.create_session(
        Session(id="subagent-session", agent="stock", title="Stock session")
    )

    mock_client = MagicMock()
    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        agent = TestAgent(CapabilityRegistry(), store)

    agent._loop.run = AsyncMock(return_value="done")  # type: ignore[attr-defined]
    response = await agent.run(
        "Check this thesis",
        "subagent-session",
        agent_name="stock",
    )

    assert response == "done"
    stock_messages = await store.get_messages("subagent-session", agent="stock")
    assert [message["role"] for message in stock_messages] == ["user", "assistant"]
    assert stock_messages[0]["content"] == "Check this thesis"
    sebastian_messages = await store.get_messages("subagent-session", agent="sebastian")
    assert sebastian_messages == []
