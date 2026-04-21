from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _build_app(authenticated: bool = True) -> FastAPI:
    from sebastian.gateway.auth import require_auth
    from sebastian.gateway.routes import memory_settings

    app = FastAPI()

    if authenticated:

        async def _fake_auth() -> dict[str, str]:
            return {"user_id": "test"}

        app.dependency_overrides[require_auth] = _fake_auth

    app.include_router(memory_settings.router, prefix="/api/v1")
    return app


@pytest.fixture
async def db_factory() -> AsyncIterator[async_sessionmaker]:
    from sebastian.store.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def test_default_memory_enabled_setting_is_true() -> None:
    from sebastian.config import settings

    assert settings.sebastian_memory_enabled is True


def test_memory_enabled_env_false_disables_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.config import Settings

    monkeypatch.setenv("SEBASTIAN_MEMORY_ENABLED", "false")

    loaded = Settings()

    assert loaded.sebastian_memory_enabled is False


@pytest.mark.asyncio
async def test_get_memory_settings_returns_enabled_by_default() -> None:
    import sebastian.gateway.state as state
    from sebastian.gateway.state import MemoryRuntimeSettings

    state.memory_settings = MemoryRuntimeSettings(enabled=True)
    app = _build_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/memory/settings")

    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}


@pytest.mark.asyncio
async def test_put_memory_settings_can_disable_memory(db_factory) -> None:
    import sebastian.gateway.state as state
    from sebastian.gateway.state import MemoryRuntimeSettings

    state.memory_settings = MemoryRuntimeSettings(enabled=True)
    state.db_factory = db_factory
    app = _build_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put("/api/v1/memory/settings", json={"enabled": False})

    assert resp.status_code == 200
    assert resp.json() == {"enabled": False}
    assert state.memory_settings.enabled is False


@pytest.mark.asyncio
async def test_put_memory_settings_can_re_enable_memory(db_factory) -> None:
    import sebastian.gateway.state as state
    from sebastian.gateway.state import MemoryRuntimeSettings

    state.memory_settings = MemoryRuntimeSettings(enabled=False)
    state.db_factory = db_factory
    app = _build_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put("/api/v1/memory/settings", json={"enabled": True})

    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}
    assert state.memory_settings.enabled is True


@pytest.mark.asyncio
async def test_get_memory_settings_requires_auth() -> None:
    app = _build_app(authenticated=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/memory/settings")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_memory_settings_requires_auth() -> None:
    app = _build_app(authenticated=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put("/api/v1/memory/settings", json={"enabled": False})

    assert resp.status_code == 401
