from __future__ import annotations

from sebastian.core.types import Session, SessionStatus


def test_session_status_includes_new_values():
    assert SessionStatus.COMPLETED == "completed"
    assert SessionStatus.FAILED == "failed"
    assert SessionStatus.STALLED == "stalled"
    assert SessionStatus.CANCELLED == "cancelled"


def test_session_has_depth_and_parent():
    s = Session(
        agent_type="code",
        title="test",
        depth=2,
    )
    assert s.depth == 2
    assert s.parent_session_id is None
    assert s.last_activity_at is not None


def test_session_no_agent_id():
    s = Session(agent_type="code", title="test", depth=1)
    assert "agent_id" not in s.model_fields
