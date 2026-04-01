from __future__ import annotations
"""Module-level singletons initialized at startup via app lifespan."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sebastian.orchestrator.sebas import Sebastian
    from sebastian.gateway.sse import SSEManager
    from sebastian.protocol.events.bus import EventBus
    from sebastian.orchestrator.conversation import ConversationManager
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

sebastian: "Sebastian"
sse_manager: "SSEManager"
event_bus: "EventBus"
conversation: "ConversationManager"
session_factory: "async_sessionmaker[AsyncSession]"
