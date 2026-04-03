from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sebastian.core.stream_events import (
    TextBlockStart,
    TextBlockStop,
    TextDelta,
    ThinkingBlockStart,
    ThinkingBlockStop,
    ThinkingDelta,
    ToolCallBlockStart,
    ToolCallReady,
    ToolResult,
    TurnDone,
)


class _MockMessageStream:
    def __init__(
        self,
        raw_events: list[Any],
        content_blocks: list[Any],
        stop_reason: str,
    ) -> None:
        self._raw_events = raw_events
        self.current_message = MagicMock()
        self.current_message.content = content_blocks
        self._final_message = MagicMock()
        self._final_message.stop_reason = stop_reason
        self.get_final_message = AsyncMock(return_value=self._final_message)

    def __aiter__(self) -> Any:
        async def _iter() -> Any:
            for event in self._raw_events:
                yield event

        return _iter()


class _MockStreamManager:
    def __init__(self, stream: _MockMessageStream) -> None:
        self._stream = stream

    async def __aenter__(self) -> _MockMessageStream:
        return self._stream

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


def _make_content_block_start(
    index: int,
    block_type: str,
    *,
    tool_id: str = "",
    name: str = "",
) -> MagicMock:
    event = MagicMock()
    event.type = "content_block_start"
    event.index = index
    event.content_block = MagicMock()
    event.content_block.type = block_type
    event.content_block.id = tool_id
    event.content_block.name = name
    return event


def _make_thinking_delta(index: int, text: str) -> MagicMock:
    event = MagicMock()
    event.type = "content_block_delta"
    event.index = index
    event.delta = MagicMock()
    event.delta.type = "thinking_delta"
    event.delta.thinking = text
    return event


def _make_text_delta(index: int, text: str) -> MagicMock:
    event = MagicMock()
    event.type = "content_block_delta"
    event.index = index
    event.delta = MagicMock()
    event.delta.type = "text_delta"
    event.delta.text = text
    return event


def _make_content_block_stop(index: int) -> MagicMock:
    event = MagicMock()
    event.type = "content_block_stop"
    event.index = index
    return event


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_thinking_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "thinking"
    block.thinking = text
    return block


def _make_tool_block(tool_id: str, tool_name: str, tool_input: dict[str, Any]) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = tool_input
    return block


def _build_mock_client(*turns: tuple[list[Any], list[Any], str]) -> MagicMock:
    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = MagicMock()
    mock_client.messages.stream = MagicMock(
        side_effect=[
            _MockStreamManager(_MockMessageStream(raw_events, content_blocks, stop_reason))
            for raw_events, content_blocks, stop_reason in turns
        ]
    )
    return mock_client


async def _collect_events(gen: Any) -> list[object]:
    events: list[object] = []
    try:
        while True:
            events.append(await gen.asend(None))
    except StopAsyncIteration:
        return events


@pytest.mark.asyncio
async def test_agent_loop_streams_thinking_and_text_blocks_then_turn_done() -> None:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.core.agent_loop import AgentLoop

    mock_client = _build_mock_client(
        (
            [
                _make_content_block_start(0, "thinking"),
                _make_thinking_delta(0, "Need to inspect."),
                _make_content_block_stop(0),
                _make_content_block_start(1, "text"),
                _make_text_delta(1, "Hello there!"),
                _make_content_block_stop(1),
            ],
            [
                _make_thinking_block("Need to inspect."),
                _make_text_block("Hello there!"),
            ],
            "end_turn",
        )
    )

    loop = AgentLoop(mock_client, CapabilityRegistry())

    events = await _collect_events(
        loop.stream(
            system_prompt="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        )
    )

    assert events == [
        ThinkingBlockStart(block_id="b0_0"),
        ThinkingDelta(block_id="b0_0", delta="Need to inspect."),
        ThinkingBlockStop(block_id="b0_0"),
        TextBlockStart(block_id="b0_1"),
        TextDelta(block_id="b0_1", delta="Hello there!"),
        TextBlockStop(block_id="b0_1"),
        TurnDone(full_text="Hello there!"),
    ]
    mock_client.messages.stream.assert_called_once()
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_agent_loop_ends_after_single_no_tool_turn() -> None:
    from sebastian.capabilities.registry import CapabilityRegistry
    from sebastian.core.agent_loop import AgentLoop

    mock_client = _build_mock_client(
        (
            [
                _make_content_block_start(0, "text"),
                _make_text_delta(0, "Done."),
                _make_content_block_stop(0),
            ],
            [_make_text_block("Done.")],
            "end_turn",
        )
    )

    loop = AgentLoop(mock_client, CapabilityRegistry())
    gen = loop.stream(system_prompt="sys", messages=[{"role": "user", "content": "Hi"}])

    assert await gen.asend(None) == TextBlockStart(block_id="b0_0")
    assert await gen.asend(None) == TextDelta(block_id="b0_0", delta="Done.")
    assert await gen.asend(None) == TextBlockStop(block_id="b0_0")
    assert await gen.asend(None) == TurnDone(full_text="Done.")

    with pytest.raises(StopAsyncIteration):
        await gen.asend(None)

    assert mock_client.messages.stream.call_count == 1
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_agent_loop_accepts_injected_tool_result_and_continues() -> None:
    from sebastian.core.agent_loop import AgentLoop

    mock_client = _build_mock_client(
        (
            [
                _make_content_block_start(0, "text"),
                _make_text_delta(0, "Checking..."),
                _make_content_block_stop(0),
                _make_content_block_start(
                    1,
                    "tool_use",
                    tool_id="toolu_1",
                    name="weather_lookup",
                ),
                _make_content_block_stop(1),
            ],
            [
                _make_text_block("Checking..."),
                _make_tool_block("toolu_1", "weather_lookup", {"city": "Shanghai"}),
            ],
            "tool_use",
        ),
        (
            [
                _make_content_block_start(0, "text"),
                _make_text_delta(0, "It is sunny."),
                _make_content_block_stop(0),
            ],
            [_make_text_block("It is sunny.")],
            "end_turn",
        ),
    )

    registry = MagicMock()
    registry.get_all_tool_specs.return_value = [
        {
            "name": "weather_lookup",
            "description": "Lookup weather",
            "input_schema": {"type": "object"},
        }
    ]

    loop = AgentLoop(mock_client, registry)
    gen = loop.stream(
        system_prompt="sys",
        messages=[{"role": "user", "content": "What's the weather?"}],
    )

    assert await gen.asend(None) == TextBlockStart(block_id="b0_0")
    assert await gen.asend(None) == TextDelta(block_id="b0_0", delta="Checking...")
    assert await gen.asend(None) == TextBlockStop(block_id="b0_0")
    assert await gen.asend(None) == ToolCallBlockStart(
        block_id="b0_1",
        tool_id="toolu_1",
        name="weather_lookup",
    )
    assert await gen.asend(None) == ToolCallReady(
        block_id="b0_1",
        tool_id="toolu_1",
        name="weather_lookup",
        inputs={"city": "Shanghai"},
    )

    injected_result = ToolResult(
        tool_id="toolu_1",
        name="weather_lookup",
        ok=True,
        output="Sunny",
        error=None,
    )

    assert await gen.asend(injected_result) == TextBlockStart(block_id="b1_0")
    assert await gen.asend(None) == TextDelta(block_id="b1_0", delta="It is sunny.")
    assert await gen.asend(None) == TextBlockStop(block_id="b1_0")
    assert await gen.asend(None) == TurnDone(full_text="Checking...It is sunny.")

    second_call = mock_client.messages.stream.call_args_list[1]
    second_messages = second_call.kwargs["messages"]

    assert second_messages[1] == {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Checking..."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "weather_lookup",
                "input": {"city": "Shanghai"},
            },
        ],
    }
    assert second_messages[2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": "Sunny",
            }
        ],
    }
    registry.call.assert_not_called()
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_agent_loop_rejects_missing_tool_result_injection() -> None:
    from sebastian.core.agent_loop import AgentLoop

    mock_client = _build_mock_client(
        (
            [
                _make_content_block_start(
                    0,
                    "tool_use",
                    tool_id="toolu_1",
                    name="weather_lookup",
                ),
                _make_content_block_stop(0),
            ],
            [_make_tool_block("toolu_1", "weather_lookup", {"city": "Shanghai"})],
            "tool_use",
        )
    )

    loop = AgentLoop(mock_client, MagicMock(get_all_tool_specs=MagicMock(return_value=[])))
    gen = loop.stream(system_prompt="sys", messages=[{"role": "user", "content": "weather"}])

    assert await gen.asend(None) == ToolCallBlockStart(
        block_id="b0_0",
        tool_id="toolu_1",
        name="weather_lookup",
    )
    assert await gen.asend(None) == ToolCallReady(
        block_id="b0_0",
        tool_id="toolu_1",
        name="weather_lookup",
        inputs={"city": "Shanghai"},
    )

    with pytest.raises(RuntimeError, match="requires an injected ToolResult"):
        await gen.asend(None)


@pytest.mark.asyncio
async def test_agent_loop_rejects_mismatched_tool_result_injection() -> None:
    from sebastian.core.agent_loop import AgentLoop

    mock_client = _build_mock_client(
        (
            [
                _make_content_block_start(
                    0,
                    "tool_use",
                    tool_id="toolu_1",
                    name="weather_lookup",
                ),
                _make_content_block_stop(0),
            ],
            [_make_tool_block("toolu_1", "weather_lookup", {"city": "Shanghai"})],
            "tool_use",
        )
    )

    loop = AgentLoop(mock_client, MagicMock(get_all_tool_specs=MagicMock(return_value=[])))
    gen = loop.stream(system_prompt="sys", messages=[{"role": "user", "content": "weather"}])

    assert await gen.asend(None) == ToolCallBlockStart(
        block_id="b0_0",
        tool_id="toolu_1",
        name="weather_lookup",
    )
    assert await gen.asend(None) == ToolCallReady(
        block_id="b0_0",
        tool_id="toolu_1",
        name="weather_lookup",
        inputs={"city": "Shanghai"},
    )

    with pytest.raises(RuntimeError, match="does not match current tool call"):
        await gen.asend(
            ToolResult(
                tool_id="toolu_2",
                name="other_tool",
                ok=True,
                output="Sunny",
                error=None,
            )
        )


@pytest.mark.asyncio
async def test_agent_loop_formats_failed_tool_result_for_next_turn() -> None:
    from sebastian.core.agent_loop import AgentLoop

    mock_client = _build_mock_client(
        (
            [
                _make_content_block_start(
                    0,
                    "tool_use",
                    tool_id="toolu_1",
                    name="weather_lookup",
                ),
                _make_content_block_stop(0),
            ],
            [_make_tool_block("toolu_1", "weather_lookup", {"city": "Shanghai"})],
            "tool_use",
        ),
        (
            [
                _make_content_block_start(0, "text"),
                _make_text_delta(0, "Fallback."),
                _make_content_block_stop(0),
            ],
            [_make_text_block("Fallback.")],
            "end_turn",
        ),
    )

    loop = AgentLoop(mock_client, MagicMock(get_all_tool_specs=MagicMock(return_value=[])))
    gen = loop.stream(system_prompt="sys", messages=[{"role": "user", "content": "weather"}])

    assert await gen.asend(None) == ToolCallBlockStart(
        block_id="b0_0",
        tool_id="toolu_1",
        name="weather_lookup",
    )
    assert await gen.asend(None) == ToolCallReady(
        block_id="b0_0",
        tool_id="toolu_1",
        name="weather_lookup",
        inputs={"city": "Shanghai"},
    )
    assert await gen.asend(
        ToolResult(
            tool_id="toolu_1",
            name="weather_lookup",
            ok=False,
            output=None,
            error="network down",
        )
    ) == TextBlockStart(block_id="b1_0")
    assert await gen.asend(None) == TextDelta(block_id="b1_0", delta="Fallback.")
    assert await gen.asend(None) == TextBlockStop(block_id="b1_0")
    assert await gen.asend(None) == TurnDone(full_text="Fallback.")

    second_call = mock_client.messages.stream.call_args_list[1]
    assert second_call.kwargs["messages"][2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": "Error: network down",
            }
        ],
    }
