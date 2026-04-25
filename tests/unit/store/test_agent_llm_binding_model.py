from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sebastian.store import models  # noqa: F401
from sebastian.store.database import Base, _install_sqlite_fk_pragma


@pytest.mark.asyncio
async def test_llm_account_record_tablename() -> None:
    from sebastian.store.models import LLMAccountRecord

    assert LLMAccountRecord.__tablename__ == "llm_accounts"


@pytest.mark.asyncio
async def test_llm_custom_model_record_tablename() -> None:
    from sebastian.store.models import LLMCustomModelRecord

    assert LLMCustomModelRecord.__tablename__ == "llm_custom_models"


@pytest.mark.asyncio
async def test_agent_binding_record_tablename() -> None:
    from sebastian.store.models import AgentLLMBindingRecord

    assert AgentLLMBindingRecord.__tablename__ == "agent_llm_bindings"


@pytest.mark.asyncio
async def test_agent_binding_has_account_and_model_columns() -> None:
    from sebastian.store.models import AgentLLMBindingRecord

    mapper = AgentLLMBindingRecord.__mapper__
    col_names = {c.key for c in mapper.column_attrs}
    assert "account_id" in col_names
    assert "model_id" in col_names
    assert "thinking_effort" in col_names


@pytest.mark.asyncio
async def test_agent_binding_has_no_provider_id_column() -> None:
    from sebastian.store.models import AgentLLMBindingRecord

    mapper = AgentLLMBindingRecord.__mapper__
    col_names = {c.key for c in mapper.column_attrs}
    assert "provider_id" not in col_names


@pytest.mark.asyncio
async def test_agent_binding_record_can_insert_and_load() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _install_sqlite_fk_pragma(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from sebastian.store.models import AgentLLMBindingRecord

    async with factory() as session:
        binding = AgentLLMBindingRecord(
            agent_type="forge",
            account_id="acc-1",
            model_id="claude-opus-4-6",
        )
        session.add(binding)
        await session.commit()

    async with factory() as session:
        result = await session.execute(select(AgentLLMBindingRecord))
        loaded = result.scalars().all()
        assert len(loaded) == 1
        assert loaded[0].agent_type == "forge"
        assert loaded[0].account_id == "acc-1"
        assert loaded[0].model_id == "claude-opus-4-6"
        assert isinstance(loaded[0].updated_at, datetime)
    await engine.dispose()


@pytest.mark.asyncio
async def test_new_binding_defaults_to_no_thinking(db_session) -> None:
    from sebastian.store.models import AgentLLMBindingRecord

    rec = AgentLLMBindingRecord(
        agent_type="foo",
        account_id="acc-1",
        model_id="model-a",
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)

    assert rec.thinking_effort is None
