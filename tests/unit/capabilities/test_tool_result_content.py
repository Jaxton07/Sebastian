from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sebastian.core.agent_loop import _is_empty_output, _tool_result_content
from sebastian.core.stream_events import (
    ProviderCallEnd,
    ToolCallBlockStart,
    ToolCallReady,
    ToolResult,
)
from sebastian.core.tool_context import get_tool_context
from sebastian.core.types import ToolResult as CoreToolResult
from sebastian.permissions.types import PermissionTier

# ---------------------------------------------------------------------------
# _is_empty_output
# ---------------------------------------------------------------------------


class TestIsEmptyOutput:
    def test_none_is_empty(self) -> None:
        assert _is_empty_output(None) is True

    def test_empty_string_is_empty(self) -> None:
        assert _is_empty_output("") is True

    def test_empty_list_is_empty(self) -> None:
        assert _is_empty_output([]) is True

    def test_empty_dict_is_empty(self) -> None:
        assert _is_empty_output({}) is True

    def test_nonempty_string_is_not_empty(self) -> None:
        assert _is_empty_output("hello") is False

    def test_nonempty_dict_is_not_empty(self) -> None:
        assert _is_empty_output({"key": "val"}) is False

    def test_nonempty_list_is_not_empty(self) -> None:
        assert _is_empty_output(["item"]) is False

    def test_zero_is_not_empty(self) -> None:
        assert _is_empty_output(0) is False

    def test_false_is_not_empty(self) -> None:
        assert _is_empty_output(False) is False


# ---------------------------------------------------------------------------
# _tool_result_content
# ---------------------------------------------------------------------------


def _make_result(
    *,
    ok: bool = True,
    output: object = None,
    error: str | None = None,
    empty_hint: str | None = None,
) -> ToolResult:
    return ToolResult(
        tool_id="t1",
        name="test_tool",
        ok=ok,
        output=output,
        error=error,
        empty_hint=empty_hint,
    )


class TestToolResultContent:
    def test_error_result(self) -> None:
        r = _make_result(ok=False, error="timeout")
        assert _tool_result_content(r) == "Error: timeout"

    def test_empty_hint_takes_priority_over_nonempty_output(self) -> None:
        r = _make_result(output={"data": 1}, empty_hint="没有找到匹配项")
        assert _tool_result_content(r) == "没有找到匹配项"

    def test_none_output_without_hint(self) -> None:
        r = _make_result(output=None)
        assert _tool_result_content(r) == "<empty output>"

    def test_empty_string_output_without_hint(self) -> None:
        r = _make_result(output="")
        assert _tool_result_content(r) == "<empty output>"

    def test_empty_dict_output_without_hint(self) -> None:
        r = _make_result(output={})
        assert _tool_result_content(r) == "<empty output>"

    def test_none_output_with_hint(self) -> None:
        r = _make_result(output=None, empty_hint="查询结果为空")
        assert _tool_result_content(r) == "查询结果为空"

    def test_nonempty_string_output(self) -> None:
        r = _make_result(output="some text")
        assert _tool_result_content(r) == "some text"

    def test_nonempty_dict_output_uses_json(self) -> None:
        output = {"stdout": "hello", "returncode": 0}
        r = _make_result(output=output)
        assert _tool_result_content(r) == '{"stdout": "hello", "returncode": 0}'

    def test_text_file_artifact_uses_lightweight_content(self) -> None:
        output = {
            "artifact": {
                "kind": "text_file",
                "attachment_id": "att-1",
                "filename": "test.txt",
                "mime_type": "text/plain",
                "size_bytes": 25,
                "download_url": "/api/v1/attachments/att-1",
                "text_excerpt": "private file content",
            }
        }
        content = _tool_result_content(_make_result(output=output))
        assert content == "已向用户发送文件 test.txt"
        assert "artifact" not in content
        assert "attachment_id" not in content
        assert "download_url" not in content
        assert "text_excerpt" not in content
        assert "private file content" not in content

    def test_image_artifact_uses_lightweight_content(self) -> None:
        output = {
            "artifact": {
                "kind": "image",
                "attachment_id": "att-2",
                "filename": "photo.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 1024,
                "download_url": "/api/v1/attachments/att-2",
                "thumbnail_url": "/api/v1/attachments/att-2/thumbnail",
            }
        }
        content = _tool_result_content(_make_result(output=output))
        assert content == "已向用户发送图片 photo.jpg"
        assert "artifact" not in content
        assert "attachment_id" not in content
        assert "download_url" not in content

    def test_nonempty_dict_output_preserves_chinese(self) -> None:
        output = {"msg": "你好"}
        r = _make_result(output=output)
        assert _tool_result_content(r) == '{"msg": "你好"}'

    def test_nonempty_list_output_uses_json(self) -> None:
        r = _make_result(output=["a", "b"])
        assert _tool_result_content(r) == '["a", "b"]'

    def test_unserializable_output_uses_default_str_path(self) -> None:
        class Opaque:
            def __str__(self) -> str:
                return "opaque-value"

        r = _make_result(output=Opaque())
        # json.dumps(default=str) calls str() on the unknown type → JSON string literal
        assert _tool_result_content(r) == '"opaque-value"'

    def test_circular_reference_falls_back_to_raw_str(self) -> None:
        circular: dict = {}
        circular["self"] = circular
        r = _make_result(output=circular)
        # json.dumps raises ValueError on circular ref → fallback to str(output)
        content = _tool_result_content(r)
        # Python repr 会显示 {'self': {...}}
        assert "self" in content
        assert "..." in content  # Python's repr of circular dict marks the cycle


# ---------------------------------------------------------------------------
# Provider capability in tool context
# ---------------------------------------------------------------------------


_SUPPORTS_IMAGE_CONTEXT_TOOL = "__test_supports_image_context"


async def _supports_image_context_tool() -> CoreToolResult:
    ctx = get_tool_context()
    assert ctx is not None
    return CoreToolResult(ok=True, output={"supports": ctx.supports_image_input})


def _register_supports_image_context_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from sebastian.core.tool import ToolSpec, _tools

    spec = ToolSpec(
        name=_SUPPORTS_IMAGE_CONTEXT_TOOL,
        description="Return provider image-input support from the current tool context.",
        parameters={"type": "object", "properties": {}, "required": []},
        permission_tier=PermissionTier.LOW,
    )
    monkeypatch.setitem(_tools, _SUPPORTS_IMAGE_CONTEXT_TOOL, (spec, _supports_image_context_tool))


def _make_policy_gate() -> Any:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.permissions.gate import PolicyGate

    approval_manager = MagicMock()
    approval_manager.request_approval = AsyncMock(return_value=True)
    reviewer = MagicMock()
    return PolicyGate(CapabilityRegistry(), reviewer, approval_manager)


async def _noop_publish(*_args: Any, **_kwargs: Any) -> None:
    return None


def _make_supports_tool_event() -> ToolCallReady:
    return ToolCallReady(
        block_id="blk_0",
        tool_id="toolu_supports_image",
        name=_SUPPORTS_IMAGE_CONTEXT_TOOL,
        inputs={},
    )


@pytest.mark.asyncio
async def test_dispatch_tool_call_passes_provider_image_capability_to_tool_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.core.stream_helpers import dispatch_tool_call

    _register_supports_image_context_tool(monkeypatch)
    gate = _make_policy_gate()

    async def call_dispatch(*, supports_image_input: bool) -> ToolResult:
        result, _ = await dispatch_tool_call(
            _make_supports_tool_event(),
            session_id="sess-provider-context",
            task_id=None,
            agent_context="sebastian",
            assistant_turn_id="turn-1",
            assistant_blocks=[],
            current_pci=0,
            block_index=0,
            gate_call=gate.call,
            update_activity=AsyncMock(),
            publish=_noop_publish,
            current_task_goals={},
            current_depth={},
            allowed_tools=[_SUPPORTS_IMAGE_CONTEXT_TOOL],
            pending_blocks={},
            supports_image_input=supports_image_input,
        )
        return result

    true_result = await call_dispatch(supports_image_input=True)
    assert true_result.output == {"supports": True}

    false_result = await call_dispatch(supports_image_input=False)
    assert false_result.output == {"supports": False}


def _extract_tool_result_supports(provider: Any) -> bool:
    tool_result_message = provider.last_messages[-1]
    content = tool_result_message["content"][0]["content"]
    return bool(json.loads(content)["supports"])


async def _run_agent_with_tool_provider(
    *,
    tmp_path: Any,
    provider: Any | None = None,
    llm_registry: Any | None = None,
    provider_supports_image_input: bool = False,
) -> bool:
    from sebastian.core.base_agent import BaseAgent
    from sebastian.core.types import Session
    from sebastian.store.session_store import SessionStore

    class TestAgent(BaseAgent):
        name = "test_agent"
        allowed_tools = [_SUPPORTS_IMAGE_CONTEXT_TOOL]

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir)
    await store.create_session(
        Session(id="provider-capability-session", agent_type="test_agent", title="Provider")
    )

    gate = _make_policy_gate()
    agent = TestAgent(
        gate=gate,
        session_store=store,
        provider=provider,
        llm_registry=llm_registry,
        provider_supports_image_input=provider_supports_image_input,
    )

    await agent.run_streaming("check capability", "provider-capability-session")

    active_provider = provider
    if active_provider is None:
        active_provider = (await llm_registry.get_provider("test_agent")).provider
    return _extract_tool_result_supports(active_provider)


def _make_tool_call_provider() -> Any:
    from tests.unit.core.test_agent_loop import MockLLMProvider

    return MockLLMProvider(
        [
            ToolCallBlockStart(
                block_id="b0_0",
                tool_id="toolu_supports_image",
                name=_SUPPORTS_IMAGE_CONTEXT_TOOL,
            ),
            _make_supports_tool_event(),
            ProviderCallEnd(stop_reason="tool_use"),
        ],
        [
            ProviderCallEnd(stop_reason="end_turn"),
        ],
    )


@pytest.mark.asyncio
async def test_base_agent_propagates_registry_provider_image_capability_to_tool_context(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.llm.registry import ResolvedProvider

    _register_supports_image_context_tool(monkeypatch)
    provider = _make_tool_call_provider()
    resolved = ResolvedProvider(
        provider=provider,
        model="fake",
        context_window_tokens=200000,
        thinking_effort=None,
        capability=None,
        thinking_format=None,
        account_id="test-account",
        model_display_name="Fake",
        supports_image_input=True,
    )
    registry = MagicMock()
    registry.get_provider = AsyncMock(return_value=resolved)

    supports = await _run_agent_with_tool_provider(tmp_path=tmp_path, llm_registry=registry)

    assert supports is True


@pytest.mark.asyncio
async def test_base_agent_direct_provider_image_capability_is_explicit(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_supports_image_context_tool(monkeypatch)

    implicit_provider = _make_tool_call_provider()
    implicit_provider.supports_image_input = True
    implicit_supports = await _run_agent_with_tool_provider(
        tmp_path=tmp_path,
        provider=implicit_provider,
    )

    explicit_provider = _make_tool_call_provider()
    explicit_supports = await _run_agent_with_tool_provider(
        tmp_path=tmp_path,
        provider=explicit_provider,
        provider_supports_image_input=True,
    )

    assert implicit_supports is False
    assert explicit_supports is True
