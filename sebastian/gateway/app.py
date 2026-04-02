from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import sebastian.gateway.state as state
    from sebastian.config import ensure_data_dir, settings
    from sebastian.capabilities.registry import registry
    from sebastian.capabilities.tools._loader import load_tools
    from sebastian.capabilities.mcps._loader import load_mcps, connect_all
    from sebastian.core.task_manager import TaskManager
    from sebastian.gateway.sse import SSEManager
    from sebastian.orchestrator.conversation import ConversationManager
    from sebastian.orchestrator.sebas import Sebastian
    from sebastian.protocol.events.bus import bus
    from sebastian.store.database import get_session_factory, init_db
    from sebastian.store.index_store import IndexStore
    from sebastian.store.session_store import SessionStore

    ensure_data_dir()
    await init_db()
    db_factory = get_session_factory()
    session_store = SessionStore(settings.sessions_dir)
    index_store = IndexStore(settings.sessions_dir)

    load_tools()

    mcp_clients = load_mcps()
    if mcp_clients:
        await connect_all(mcp_clients, registry)

    event_bus = bus
    conversation = ConversationManager(event_bus)
    task_manager = TaskManager(session_store, event_bus)
    sse_mgr = SSEManager(event_bus)
    sebastian_agent = Sebastian(
        registry=registry,
        session_store=session_store,
        index_store=index_store,
        task_manager=task_manager,
        conversation=conversation,
        event_bus=event_bus,
    )

    state.sebastian = sebastian_agent
    state.sse_manager = sse_mgr
    state.event_bus = event_bus
    state.conversation = conversation
    state.session_store = session_store
    state.index_store = index_store
    state.db_factory = db_factory

    logger.info("Sebastian gateway started")
    yield
    logger.info("Sebastian gateway shutdown")


def create_app() -> FastAPI:
    from sebastian.gateway.routes import agents, approvals, sessions, stream, turns

    app = FastAPI(title="Sebastian Gateway", version="0.1.0", lifespan=lifespan)
    app.include_router(turns.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(approvals.router, prefix="/api/v1")
    app.include_router(stream.router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")
    return app


app = create_app()
