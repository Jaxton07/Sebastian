from __future__ import annotations

import asyncio

_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


def get_session_lock(session_id: str) -> asyncio.Lock:
    lock = _SESSION_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _SESSION_LOCKS[session_id] = lock
    return lock


def release_session_lock(session_id: str) -> None:
    """Drop the per-session lock once the session reached a terminal state.

    仅在 session 进入终态（COMPLETED / FAILED / CANCELLED）后调用；IDLE/WAITING
    可能被 resume，仍然需要保留锁。若当前锁正被持有则保留（下一个终态再试）。
    """
    lock = _SESSION_LOCKS.get(session_id)
    if lock is None:
        return
    if lock.locked():
        return
    _SESSION_LOCKS.pop(session_id, None)
