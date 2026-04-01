from __future__ import annotations
import asyncio
import pytest


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType

    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    await bus.publish(Event(type=EventType.TASK_CREATED, data={"task_id": "t1"}))
    assert len(received) == 1
    assert received[0].type == EventType.TASK_CREATED


@pytest.mark.asyncio
async def test_subscribe_filtered_by_type():
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType

    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler, EventType.TASK_COMPLETED)
    await bus.publish(Event(type=EventType.TASK_CREATED, data={}))
    await bus.publish(Event(type=EventType.TASK_COMPLETED, data={}))
    assert len(received) == 1
    assert received[0].type == EventType.TASK_COMPLETED


@pytest.mark.asyncio
async def test_unsubscribe():
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType

    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    bus.unsubscribe(handler)
    await bus.publish(Event(type=EventType.TASK_CREATED, data={}))
    assert len(received) == 0


@pytest.mark.asyncio
async def test_handler_exception_does_not_crash_bus():
    from sebastian.protocol.events.bus import EventBus
    from sebastian.protocol.events.types import Event, EventType

    bus = EventBus()
    good_received: list[Event] = []

    async def bad_handler(event: Event) -> None:
        raise RuntimeError("oops")

    async def good_handler(event: Event) -> None:
        good_received.append(event)

    bus.subscribe(bad_handler)
    bus.subscribe(good_handler)
    await bus.publish(Event(type=EventType.TASK_CREATED, data={}))
    assert len(good_received) == 1
