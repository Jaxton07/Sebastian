from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sebastian.memory.entity_registry import EntityRegistry
from sebastian.store import models  # noqa: F401
from sebastian.store.database import Base


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_upsert_entity_creates_with_correct_fields(db_session) -> None:
    registry = EntityRegistry(db_session)

    record = await registry.upsert_entity("小橘", "pet", aliases=["橘猫"])
    await db_session.flush()

    assert record.canonical_name == "小橘"
    assert record.entity_type == "pet"
    assert "橘猫" in record.aliases
    assert record.id is not None
    assert isinstance(record.created_at, datetime)
    assert isinstance(record.updated_at, datetime)


async def test_upsert_entity_merges_aliases_without_duplicates(db_session) -> None:
    registry = EntityRegistry(db_session)

    await registry.upsert_entity("小橘", "pet", aliases=["橘猫"])
    await db_session.flush()

    # Re-upsert with overlapping and new alias
    record = await registry.upsert_entity("小橘", "pet", aliases=["橘猫", "小橘子"])
    await db_session.flush()

    assert record.canonical_name == "小橘"
    # aliases must contain both, with no duplicates
    assert sorted(record.aliases) == ["小橘子", "橘猫"]
    assert len(record.aliases) == len(set(record.aliases))


async def test_lookup_by_canonical_name(db_session) -> None:
    registry = EntityRegistry(db_session)

    await registry.upsert_entity("小橘", "pet", aliases=["橘猫"])
    await db_session.flush()

    results = await registry.lookup("小橘")

    assert len(results) == 1
    assert results[0].canonical_name == "小橘"


async def test_lookup_by_alias(db_session) -> None:
    registry = EntityRegistry(db_session)

    await registry.upsert_entity("小橘", "pet", aliases=["橘猫"])
    await db_session.flush()

    results = await registry.lookup("橘猫")

    assert len(results) == 1
    assert results[0].canonical_name == "小橘"


async def test_lookup_returns_empty_for_unknown_term(db_session) -> None:
    registry = EntityRegistry(db_session)

    results = await registry.lookup("不存在的实体")

    assert results == []


async def test_sync_jieba_terms_calls_add_entity_terms(db_session) -> None:
    registry = EntityRegistry(db_session)

    await registry.upsert_entity("小橘", "pet", aliases=["橘猫", "小橘子"])
    await db_session.flush()

    with patch("sebastian.memory.entity_registry.add_entity_terms") as mock_add:
        await registry.sync_jieba_terms()

    mock_add.assert_called_once()
    terms_passed = set(mock_add.call_args[0][0])
    assert "小橘" in terms_passed
    assert "橘猫" in terms_passed
    assert "小橘子" in terms_passed
