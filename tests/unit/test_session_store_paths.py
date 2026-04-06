from __future__ import annotations

import asyncio
from pathlib import Path

from sebastian.core.types import Session
from sebastian.store.session_store import SessionStore


async def _test_subagent_session_path() -> None:
    """Sub-agent sessions should be stored at {agent_type}/{session_id}/ without agent_id."""
    tmp = Path("/tmp/test_sessions_path")
    tmp.mkdir(parents=True, exist_ok=True)
    store = SessionStore(tmp)
    session = Session(id="test123", agent_type="code", title="test", depth=2)
    await store.create_session(session)
    expected_dir = tmp / "code" / "test123"
    assert expected_dir.exists(), f"Expected {expected_dir} to exist"
    # No 'subagents' in path
    assert "subagents" not in str(expected_dir)


def test_subagent_session_path() -> None:
    asyncio.run(_test_subagent_session_path())
