from __future__ import annotations

from sebastian.core.types import ModelImagePayload, Session, SessionStatus, ToolResult


def test_session_status_values():
    expected = {"active", "idle", "completed", "failed", "stalled", "waiting", "cancelled"}
    assert {s.value for s in SessionStatus} == expected


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
    assert "agent_id" not in Session.model_fields


def test_tool_result_display_defaults_to_none() -> None:
    r = ToolResult(ok=True, output={"k": "v"})
    assert r.display is None


def test_tool_result_display_accepts_string() -> None:
    r = ToolResult(ok=True, output={"k": "v"}, display="human-readable")
    assert r.display == "human-readable"


def test_tool_result_model_images_defaults_empty() -> None:
    result = ToolResult(ok=True, output={"filename": "photo.png"})
    assert result.model_images == []


def test_model_image_payload_holds_base64_data() -> None:
    payload = ModelImagePayload(media_type="image/png", data_base64="abc", filename="p.png")
    assert payload.media_type == "image/png"
    assert payload.data_base64 == "abc"
    assert payload.filename == "p.png"
