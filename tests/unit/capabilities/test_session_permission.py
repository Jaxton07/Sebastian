from __future__ import annotations

import pytest

from sebastian.capabilities.tools._session_permission import assert_session_action_permission


def _entry(depth: int, parent_session_id: str) -> dict:
    return {"depth": depth, "parent_session_id": parent_session_id}


@pytest.mark.parametrize("action", ["stop", "resume"])
def test_sebastian_depth1_always_allowed(action) -> None:
    assert (
        assert_session_action_permission(
            action=action,
            ctx_session_id="seb-1",
            ctx_depth=1,
            index_entry=_entry(3, "code-leader-1"),
            session_id="s1",
        )
        is None
    )


@pytest.mark.parametrize("action", ["stop", "resume"])
def test_leader_allowed_on_own_depth3_worker(action) -> None:
    assert (
        assert_session_action_permission(
            action=action,
            ctx_session_id="leader-A",
            ctx_depth=2,
            index_entry=_entry(3, "leader-A"),
            session_id="s1",
        )
        is None
    )


@pytest.mark.parametrize("action", ["stop", "resume"])
def test_leader_rejected_on_other_leader_worker(action) -> None:
    err = assert_session_action_permission(
        action=action,
        ctx_session_id="leader-A",
        ctx_depth=2,
        index_entry=_entry(3, "leader-B"),
        session_id="s1",
    )
    assert err is not None
    assert "无权" in err


@pytest.mark.parametrize("action", ["stop", "resume"])
def test_leader_rejected_on_depth2_session(action) -> None:
    err = assert_session_action_permission(
        action=action,
        ctx_session_id="leader-A",
        ctx_depth=2,
        index_entry=_entry(2, "seb-1"),
        session_id="s1",
    )
    assert err is not None


@pytest.mark.parametrize("action", ["stop", "resume"])
def test_depth3_worker_rejected(action) -> None:
    err = assert_session_action_permission(
        action=action,
        ctx_session_id="worker-1",
        ctx_depth=3,
        index_entry=_entry(3, "leader-A"),
        session_id="s1",
    )
    assert err is not None
    assert "Sebastian(depth=1) 或组长(depth=2)" in err


@pytest.mark.parametrize("action", ["stop", "resume"])
def test_unexpected_depth_rejected(action) -> None:
    err = assert_session_action_permission(
        action=action,
        ctx_session_id="x",
        ctx_depth=0,
        index_entry=_entry(3, "y"),
        session_id="s1",
    )
    assert err is not None
