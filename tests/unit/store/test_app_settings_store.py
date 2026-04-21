from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sebastian.store.app_settings_store import APP_SETTING_MEMORY_ENABLED, AppSettingsStore
from sebastian.store.database import Base


@pytest_asyncio.fixture
async def db_session(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db", future=True)
    async with engine.begin() as conn:
        from sebastian.store import models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(db_session) -> None:
    store = AppSettingsStore(db_session)
    assert await store.get("nonexistent") is None


@pytest.mark.asyncio
async def test_get_returns_default_when_absent(db_session) -> None:
    store = AppSettingsStore(db_session)
    assert await store.get("nonexistent", default="fallback") == "fallback"


@pytest.mark.asyncio
async def test_set_then_get_returns_value(db_session) -> None:
    store = AppSettingsStore(db_session)
    await store.set(APP_SETTING_MEMORY_ENABLED, "false")
    await db_session.commit()
    assert await store.get(APP_SETTING_MEMORY_ENABLED) == "false"


@pytest.mark.asyncio
async def test_set_upserts_on_second_call(db_session) -> None:
    store = AppSettingsStore(db_session)
    await store.set(APP_SETTING_MEMORY_ENABLED, "true")
    await db_session.commit()
    await store.set(APP_SETTING_MEMORY_ENABLED, "false")
    await db_session.commit()
    result = await store.get(APP_SETTING_MEMORY_ENABLED)
    assert result == "false"
