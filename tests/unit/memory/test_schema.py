from sqlalchemy.ext.asyncio import create_async_engine


async def test_memory_tables_created() -> None:
    """All memory tables are created by Base.metadata.create_all()."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        from sebastian.store import models  # noqa: F401 — register all models
        from sebastian.store.database import Base
        await conn.run_sync(Base.metadata.create_all)
        result = await conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in result.fetchall()}

    assert "memory_slots" in tables
    assert "profile_memories" in tables
    assert "episode_memories" in tables
    assert "entities" in tables
    assert "relation_candidates" in tables
    assert "memory_decision_log" in tables
    await engine.dispose()
