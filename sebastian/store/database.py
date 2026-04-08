from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        from sebastian.config import settings

        _engine = create_async_engine(settings.database_url, echo=False, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Create all tables. Call once at startup."""
    from sebastian.store import models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_idempotent_migrations(conn)
    logger.info("Database initialized")


async def _apply_idempotent_migrations(conn: Any) -> None:
    """Apply best-effort schema patches for columns added after initial create_all.

    Each entry: (table, column, DDL fragment). SQLite only.
    """
    patches: list[tuple[str, str, str]] = [
        ("llm_providers", "thinking_capability", "VARCHAR(20)"),
    ]
    for table, column, ddl in patches:
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
        existing = {row[1] for row in result.fetchall()}
        if column not in existing:
            await conn.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
            )
            logger.info("Applied migration: %s.%s", table, column)
