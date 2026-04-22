from __future__ import annotations

import sqlalchemy
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest.fixture
async def sqlite_session_factory():
    import sebastian.store.models  # noqa: F401 — 注册所有 ORM 类到 Base.metadata
    from sebastian.store.database import Base, _apply_idempotent_migrations
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_idempotent_migrations(conn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_storage_tables_exist(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        rows = await session.execute(sqlalchemy.text("PRAGMA table_info(sessions)"))
        columns = {row[1] for row in rows.fetchall()}
        assert {"id", "agent_type", "next_item_seq"}.issubset(columns)


@pytest.mark.asyncio
async def test_session_items_table_exists(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        rows = await session.execute(sqlalchemy.text("PRAGMA table_info(session_items)"))
        columns = {row[1] for row in rows.fetchall()}
        assert {"id", "session_id", "agent_type", "seq", "kind", "archived", "effective_seq"}.issubset(columns)


@pytest.mark.asyncio
async def test_session_todos_table_exists(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        rows = await session.execute(sqlalchemy.text("PRAGMA table_info(session_todos)"))
        columns = {row[1] for row in rows.fetchall()}
        assert {"session_id", "agent_type", "todos"}.issubset(columns)


@pytest.mark.asyncio
async def test_session_consolidations_cursor_fields_exist(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        rows = await session.execute(sqlalchemy.text("PRAGMA table_info(session_consolidations)"))
        columns = {row[1] for row in rows.fetchall()}
        assert {"last_consolidated_seq", "last_seen_item_seq", "last_consolidated_source_seq", "consolidation_mode"}.issubset(columns)
