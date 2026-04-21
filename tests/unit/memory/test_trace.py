from __future__ import annotations

import logging
from dataclasses import dataclass


def test_trace_outputs_keyword_and_event(caplog) -> None:
    from sebastian.memory.trace import trace

    caplog.set_level(logging.DEBUG, logger="sebastian.memory.trace")

    trace("unit.event", session_id="s1", count=2)

    assert "MEMORY_TRACE unit.event" in caplog.text
    assert "session_id=s1" in caplog.text
    assert "count=2" in caplog.text


def test_preview_text_truncates_and_sanitizes_newlines() -> None:
    from sebastian.memory.trace import preview_text

    text = preview_text("hello\nworld" * 20, limit=16)

    assert "\n" not in text
    assert len(text) <= 17
    assert text.endswith("…")


def test_record_ref_extracts_safe_metadata() -> None:
    from sebastian.memory.trace import record_ref

    @dataclass
    class _Record:
        id: str = "mem-1"
        kind: str = "preference"
        slot_id: str = "user.preference.language"
        status: str = "active"
        confidence: float = 0.9
        content: str = "用户偏好简洁中文回复"

    ref = record_ref(_Record())

    assert ref["id"] == "mem-1"
    assert ref["kind"] == "preference"
    assert ref["slot_id"] == "user.preference.language"
    assert ref["preview"] == "用户偏好简洁中文回复"


def test_record_ref_tolerates_missing_fields() -> None:
    from sebastian.memory.trace import record_ref

    ref = record_ref(object())

    assert isinstance(ref, dict)
