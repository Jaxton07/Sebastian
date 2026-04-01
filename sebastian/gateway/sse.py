from __future__ import annotations
import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sebastian.protocol.events.bus import EventBus
from sebastian.protocol.events.types import Event

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages active SSE client connections. Subscribes to the global EventBus
    and broadcasts all events to connected clients as SSE-formatted strings."""

    def __init__(self, event_bus: EventBus) -> None:
        self._queues: list[asyncio.Queue[Event | None]] = []
        event_bus.subscribe(self._on_event)

    async def _on_event(self, event: Event) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("SSE queue full, dropping event %s", event.type)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Async generator — yield SSE-formatted strings for one client."""
        q: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=200)
        self._queues.append(q)
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                payload = json.dumps({
                    "event": event.type.value,
                    "data": event.data | {"ts": event.ts.isoformat()},
                })
                yield f"data: {payload}\n\n"
        finally:
            if q in self._queues:
                self._queues.remove(q)
