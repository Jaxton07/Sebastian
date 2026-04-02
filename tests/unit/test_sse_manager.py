from __future__ import annotations

import asyncio
import json

import pytest


@pytest.mark.asyncio
async def test_sse_stream_payload_includes_type_key() -> None:
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
    payload = json.loads(chunk.removeprefix("data: ").strip())
    assert payload["type"] == "turn.response"
