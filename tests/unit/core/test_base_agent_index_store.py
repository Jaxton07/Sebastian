from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_update_activity_uses_session_store() -> None:
    """_update_activity 应该调用 session_store.update_activity。"""
    from sebastian.core.base_agent import BaseAgent
    from sebastian.store.session_store import SessionStore

    class TestAgent(BaseAgent):
        name = "test"
        system_prompt = "test"

    mock_session_store = MagicMock(spec=SessionStore)
    mock_session_store.update_activity = AsyncMock()

    agent = TestAgent(
        gate=MagicMock(),
        session_store=mock_session_store,
    )

    await agent._update_activity("sess-abc", "test")

    mock_session_store.update_activity.assert_awaited_once_with("sess-abc", "test")
