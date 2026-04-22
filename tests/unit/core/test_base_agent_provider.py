from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sebastian.core.stream_events import (
    ProviderCallEnd,
    TextBlockStart,
    TextBlockStop,
    TextDelta,
)
from tests.unit.core.test_agent_loop import MockLLMProvider


@pytest.mark.asyncio
async def test_base_agent_uses_injected_provider() -> None:
    """BaseAgent passes the injected LLMProvider to AgentLoop."""
    from sebastian.core.base_agent import BaseAgent
    from sebastian.store.session_store import SessionStore

    provider = MockLLMProvider(
        [
            TextBlockStart(block_id="b0_0"),
            TextDelta(block_id="b0_0", delta="Hello from sub."),
            TextBlockStop(block_id="b0_0", text="Hello from sub."),
            ProviderCallEnd(stop_reason="end_turn"),
        ]
    )

    class TestAgent(BaseAgent):
        name = "test"
        system_prompt = "You are a test agent."

    session_store = MagicMock(spec=SessionStore)
    session_store.get_session_for_agent_type = AsyncMock(return_value=MagicMock())
    session_store.update_activity = AsyncMock()
    session_store.get_messages = AsyncMock(return_value=[])
    session_store.append_message = AsyncMock()

    agent = TestAgent(
        gate=MagicMock(),
        session_store=session_store,
        provider=provider,
    )

    result = await agent.run("hi", session_id="test_sess_01")
    assert result == "Hello from sub."
    assert provider.call_count == 1
