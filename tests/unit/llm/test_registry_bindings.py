from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sebastian.llm.crypto import encrypt
from sebastian.store import models  # noqa: F401
from sebastian.store.database import Base, _install_sqlite_fk_pragma


@pytest_asyncio.fixture
async def registry_with_db(tmp_path, monkeypatch):
    key_file = tmp_path / "secret.key"
    key_file.write_text("test-secret")
    monkeypatch.setattr("sebastian.config.settings.sebastian_data_dir", str(tmp_path))

    from sebastian.llm.registry import LLMProviderRegistry

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    _install_sqlite_fk_pragma(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield LLMProviderRegistry(factory)
    await engine.dispose()


@pytest.mark.asyncio
async def test_set_and_get_binding(registry_with_db) -> None:
    from sebastian.store.models import LLMProviderRecord

    record = LLMProviderRecord(
        name="X",
        provider_type="anthropic",
        api_key_enc=encrypt("k"),
        model="claude-opus-4-6",
        is_default=False,
    )
    await registry_with_db.create(record)
    records = await registry_with_db.list_all()
    pid = records[0].id

    await registry_with_db.set_binding("forge", pid)
    bindings = await registry_with_db.list_bindings()
    assert len(bindings) == 1
    assert bindings[0].agent_type == "forge"
    assert bindings[0].provider_id == pid


@pytest.mark.asyncio
async def test_set_binding_upsert_overwrites(registry_with_db) -> None:
    from sebastian.store.models import LLMProviderRecord

    r1 = LLMProviderRecord(name="A", provider_type="anthropic", api_key_enc=encrypt("k1"), model="m1", is_default=False)
    r2 = LLMProviderRecord(name="B", provider_type="openai", api_key_enc=encrypt("k2"), model="m2", is_default=False)
    await registry_with_db.create(r1)
    await registry_with_db.create(r2)
    records = await registry_with_db.list_all()
    id_a = next(r.id for r in records if r.name == "A")
    id_b = next(r.id for r in records if r.name == "B")

    await registry_with_db.set_binding("forge", id_a)
    await registry_with_db.set_binding("forge", id_b)

    bindings = await registry_with_db.list_bindings()
    assert len(bindings) == 1
    assert bindings[0].provider_id == id_b


@pytest.mark.asyncio
async def test_set_binding_with_null_provider_id(registry_with_db) -> None:
    await registry_with_db.set_binding("forge", None)
    bindings = await registry_with_db.list_bindings()
    assert len(bindings) == 1
    assert bindings[0].agent_type == "forge"
    assert bindings[0].provider_id is None


@pytest.mark.asyncio
async def test_clear_binding_removes_row(registry_with_db) -> None:
    await registry_with_db.set_binding("forge", None)
    await registry_with_db.clear_binding("forge")
    bindings = await registry_with_db.list_bindings()
    assert bindings == []


@pytest.mark.asyncio
async def test_clear_binding_noop_when_missing(registry_with_db) -> None:
    # Should not raise
    await registry_with_db.clear_binding("nonexistent")
    assert await registry_with_db.list_bindings() == []
