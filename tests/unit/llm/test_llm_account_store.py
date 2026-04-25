from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sebastian.llm.crypto import decrypt, encrypt
from sebastian.store.database import Base, _install_sqlite_fk_pragma


@pytest.mark.asyncio
async def test_llm_account_record_roundtrip() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _install_sqlite_fk_pragma(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from sebastian.store.models import LLMAccountRecord

    async with factory() as session:
        record = LLMAccountRecord(
            name="Claude Home",
            catalog_provider_id="anthropic",
            provider_type="anthropic",
            api_key_enc=encrypt("sk-ant-test"),
        )
        session.add(record)
        await session.commit()

    async with factory() as session:
        result = await session.execute(select(LLMAccountRecord))
        loaded = result.scalar_one()
        assert loaded.name == "Claude Home"
        assert loaded.catalog_provider_id == "anthropic"
        assert loaded.provider_type == "anthropic"
        assert loaded.api_key_enc != "sk-ant-test"
        assert decrypt(loaded.api_key_enc) == "sk-ant-test"
    await engine.dispose()


@pytest.mark.asyncio
async def test_llm_custom_model_record_roundtrip() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _install_sqlite_fk_pragma(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from sebastian.store.models import LLMAccountRecord, LLMCustomModelRecord

    async with factory() as session:
        account = LLMAccountRecord(
            name="Test",
            catalog_provider_id="openai",
            provider_type="openai",
            api_key_enc=encrypt("sk-test"),
        )
        session.add(account)
        await session.flush()

        model = LLMCustomModelRecord(
            account_id=account.id,
            model_id="gpt-4o-mini",
            display_name="GPT-4o Mini",
            context_window_tokens=128000,
        )
        session.add(model)
        await session.commit()

    async with factory() as session:
        result = await session.execute(select(LLMCustomModelRecord))
        loaded = result.scalar_one()
        assert loaded.model_id == "gpt-4o-mini"
        assert loaded.display_name == "GPT-4o Mini"
        assert loaded.context_window_tokens == 128000
    await engine.dispose()


@pytest.mark.asyncio
async def test_llm_custom_model_unique_constraint() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _install_sqlite_fk_pragma(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from sebastian.store.models import LLMAccountRecord, LLMCustomModelRecord

    async with factory() as session:
        account = LLMAccountRecord(
            name="Test",
            catalog_provider_id="anthropic",
            provider_type="anthropic",
            api_key_enc=encrypt("sk-test"),
        )
        session.add(account)
        await session.flush()

        model1 = LLMCustomModelRecord(
            account_id=account.id,
            model_id="claude-sonnet-4",
            display_name="Sonnet 4",
            context_window_tokens=200000,
        )
        session.add(model1)
        await session.commit()

    async with factory() as session:
        # Duplicate account_id + model_id should violate unique constraint
        model2 = LLMCustomModelRecord(
            account_id=account.id,
            model_id="claude-sonnet-4",
            display_name="Sonnet 4 Duplicate",
            context_window_tokens=200000,
        )
        session.add(model2)
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()
