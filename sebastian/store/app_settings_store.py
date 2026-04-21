from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from sebastian.store.models import AppSettingsRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

APP_SETTING_MEMORY_ENABLED = "memory_enabled"


class AppSettingsStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str, default: str | None = None) -> str | None:
        """Return the value for *key*, or *default* if absent."""
        result = await self._session.execute(
            select(AppSettingsRecord).where(AppSettingsRecord.key == key)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return default
        return record.value

    async def set(self, key: str, value: str) -> None:
        """Upsert *key* → *value*. Caller must commit the session."""
        result = await self._session.execute(
            select(AppSettingsRecord).where(AppSettingsRecord.key == key)
        )
        record = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if record is None:
            self._session.add(AppSettingsRecord(key=key, value=value, updated_at=now))
        else:
            record.value = value
            record.updated_at = now
