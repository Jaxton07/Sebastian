from __future__ import annotations

from pathlib import Path

import pytest

from sebastian.core.types import Session
from sebastian.store.index_store import IndexStore


@pytest.fixture
def tmp_sessions_dir(tmp_path: Path) -> Path:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    return sessions_dir


@pytest.mark.asyncio
async def test_upsert_and_list(tmp_sessions_dir: Path) -> None:
    store = IndexStore(tmp_sessions_dir)
    session = Session(agent="sebastian", title="Hello")

    await store.upsert(session)

    sessions = await store.list_all()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session.id
    assert sessions[0]["agent"] == "sebastian"


@pytest.mark.asyncio
async def test_upsert_updates_existing(tmp_sessions_dir: Path) -> None:
    store = IndexStore(tmp_sessions_dir)
    session = Session(agent="sebastian", title="Original")

    await store.upsert(session)
    session.title = "Updated"
    await store.upsert(session)

    sessions = await store.list_all()
    assert len(sessions) == 1
    assert sessions[0]["title"] == "Updated"


@pytest.mark.asyncio
async def test_list_by_agent(tmp_sessions_dir: Path) -> None:
    store = IndexStore(tmp_sessions_dir)
    session_one = Session(agent="sebastian", title="Chat 1")
    session_two = Session(agent="stock", title="Stock 1")

    await store.upsert(session_one)
    await store.upsert(session_two)

    results = await store.list_by_agent("stock")
    assert len(results) == 1
    assert results[0]["agent"] == "stock"
