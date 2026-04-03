from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_chat_uses_run_streaming_without_duplicate_turn_events(
    tmp_path: Path,
) -> None:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.core.task_manager import TaskManager
    from sebastian.core.types import Session
    from sebastian.orchestrator.conversation import ConversationManager
    from sebastian.orchestrator.sebas import Sebastian
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType
    from sebastian.store.index_store import IndexStore
    from sebastian.store.session_store import SessionStore

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir)
    index_store = IndexStore(sessions_dir)
    bus = EventBus()
    conversation = ConversationManager(bus)
    task_manager = TaskManager(store, bus, index_store=index_store)

    await store.create_session(
        Session(
            id="chat-session",
            agent_type="sebastian",
            agent_id="sebastian_01",
            title="Chat session",
        )
    )

    collected_events: list[Event] = []

    async def capture(event: Event) -> None:
        collected_events.append(event)

    bus.subscribe(capture)

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

    async def fake_run_streaming(user_message: str, session_id: str) -> str:
        await bus.publish(
            Event(
                type=EventType.TURN_RECEIVED,
                data={"session_id": session_id, "message": user_message[:200]},
            )
        )
        await bus.publish(
            Event(
                type=EventType.TURN_RESPONSE,
                data={"session_id": session_id, "content": "streamed response"},
            )
        )
        return "streamed response"

    agent.run = AsyncMock(side_effect=AssertionError("run should not be called"))  # type: ignore[method-assign]
    agent.run_streaming = AsyncMock(side_effect=fake_run_streaming)  # type: ignore[method-assign]

    response = await agent.chat("hello", "chat-session")

    assert response == "streamed response"
    agent.run_streaming.assert_awaited_once_with("hello", "chat-session")
    assert [event.type for event in collected_events].count(EventType.TURN_RECEIVED) == 1
    assert [event.type for event in collected_events].count(EventType.TURN_RESPONSE) == 1


@pytest.mark.asyncio
async def test_get_or_create_session_creates_sebastian_worker_session(
    tmp_path: Path,
) -> None:
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

    session = await agent.get_or_create_session(None, "hello from sebastian")

    assert session.agent_type == "sebastian"
    assert session.agent_id == "sebastian_01"
    assert session.title == "hello from sebastian"

    loaded = await store.get_session(session.id, "sebastian", "sebastian_01")
    assert loaded is not None
    assert loaded.id == session.id


@pytest.mark.asyncio
async def test_get_or_create_session_reloads_existing_sebastian_worker_session(
    tmp_path: Path,
) -> None:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.core.task_manager import TaskManager
    from sebastian.core.types import Session
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

    existing_session = Session(
        id="existing-session",
        agent_type="sebastian",
        agent_id="sebastian_01",
        title="Persisted title",
    )
    await store.create_session(existing_session)

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

    loaded = await agent.get_or_create_session("existing-session", "ignored")

    assert loaded.id == "existing-session"
    assert loaded.agent_type == "sebastian"
    assert loaded.agent_id == "sebastian_01"
    assert loaded.title == "Persisted title"


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
