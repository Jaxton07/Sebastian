from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


def _parse_sse_chunk(chunk: str) -> tuple[int, dict[str, Any]]:
    lines = [line for line in chunk.strip().splitlines() if line]
    assert lines[0].startswith("id: ")
    assert lines[1].startswith("data: ")
    event_id = int(lines[0].removeprefix("id: ").strip())
    payload = json.loads(lines[1].removeprefix("data: ").strip())
    return event_id, payload


@pytest.mark.asyncio
async def test_sse_stream_emits_event_id_and_preserves_payload_shape() -> None:
    from sebastian.gateway.sse import SSEManager
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType

    bus = EventBus()
    manager = SSEManager(bus)
    stream = manager.stream()
    chunk_task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    await bus.publish(Event(type=EventType.TURN_RESPONSE, data={"session_id": "abc"}))
    chunk = await chunk_task
    event_id, payload = _parse_sse_chunk(chunk)
    assert event_id == 1
    assert payload["type"] == "turn.response"
    assert payload["event"] == "turn.response"
    assert payload["data"]["session_id"] == "abc"


@pytest.mark.asyncio
async def test_sse_session_stream_filters_other_sessions() -> None:
    from sebastian.gateway.sse import SSEManager
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType

    bus = EventBus()
    manager = SSEManager(bus)
    stream = manager.stream(session_id="abc")
    chunk_task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)

    await bus.publish(Event(type=EventType.TURN_RESPONSE, data={"session_id": "xyz"}))
    await asyncio.sleep(0)
    assert not chunk_task.done()

    await bus.publish(Event(type=EventType.TURN_RESPONSE, data={"session_id": "abc"}))
    chunk = await chunk_task
    event_id, payload = _parse_sse_chunk(chunk)
    assert event_id == 2
    assert payload["data"]["session_id"] == "abc"


@pytest.mark.asyncio
async def test_sse_reconnect_replays_from_last_event_id() -> None:
    from sebastian.gateway.sse import SSEManager
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType

    bus = EventBus()
    manager = SSEManager(bus)

    live_stream = manager.stream()
    live_first_task = asyncio.create_task(anext(live_stream))
    await asyncio.sleep(0)
    await bus.publish(Event(type=EventType.TURN_RESPONSE, data={"session_id": "abc", "step": 1}))
    first_chunk = await live_first_task
    first_event_id, first_payload = _parse_sse_chunk(first_chunk)
    assert first_event_id == 1
    assert first_payload["data"]["step"] == 1

    second_task = asyncio.create_task(anext(live_stream))
    await asyncio.sleep(0)
    await bus.publish(Event(type=EventType.TURN_RESPONSE, data={"session_id": "abc", "step": 2}))
    second_chunk = await second_task
    second_event_id, second_payload = _parse_sse_chunk(second_chunk)
    assert second_event_id == 2
    assert second_payload["data"]["step"] == 2
    await live_stream.aclose()

    replay_stream = manager.stream(last_event_id=1)
    replay_chunk = await anext(replay_stream)
    replay_event_id, replay_payload = _parse_sse_chunk(replay_chunk)
    assert replay_event_id == 2
    assert replay_payload["data"]["step"] == 2
    await replay_stream.aclose()
