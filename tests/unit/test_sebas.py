from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_intervene_forwards_agent_name_to_run(tmp_path: Path) -> None:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.core.task_manager import TaskManager
    from sebastian.orchestrator.conversation import ConversationManager
    from sebastian.orchestrator.sebas import Sebastian
    from sebastian.protocol.events.bus import EventBus
    from sebastian.store.index_store import IndexStore
    from sebastian.store.session_store import SessionStore

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir)
    index_store = IndexStore(sessions_dir)
    bus = EventBus()
    conversation = ConversationManager(bus)
    task_manager = TaskManager(store, bus, index_store=index_store)

    mock_client = MagicMock()
    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        agent = Sebastian(
            registry=CapabilityRegistry(),
            session_store=store,
            index_store=index_store,
            task_manager=task_manager,
            conversation=conversation,
            event_bus=bus,
        )

    agent.run = AsyncMock(return_value="done")  # type: ignore[method-assign]
    response = await agent.intervene("stock", "session-123", "revise this")

    assert response == "done"
    agent.run.assert_awaited_once_with(
        "revise this",
        "session-123",
        agent_name="stock",
    )
