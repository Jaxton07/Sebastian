from __future__ import annotations

import pytest


def test_llm_provider_is_abstract() -> None:
    from sebastian.llm.provider import LLMProvider

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        LLMProvider()  # type: ignore[abstract]


def test_llm_provider_stream_signature_accepted_by_subclass() -> None:
    from collections.abc import AsyncGenerator

    from sebastian.core.stream_events import LLMStreamEvent
    from sebastian.llm.provider import LLMProvider

    class ConcreteProvider(LLMProvider):
        async def stream(
            self,
            *,
            system: str,
            messages: list[dict],
            tools: list[dict],
            model: str,
            max_tokens: int,
            block_id_prefix: str = "",
            thinking_effort: str | None = None,
        ) -> AsyncGenerator[LLMStreamEvent, None]:
            return
            yield  # make it an async generator

    p = ConcreteProvider()
    assert hasattr(p, "stream")


@pytest.mark.asyncio
async def test_anthropic_provider_streams_text_and_ends() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from sebastian.core.stream_events import (
        ProviderCallEnd,
        TextBlockStart,
        TextBlockStop,
        TextDelta,
    )
    from sebastian.llm.anthropic import AnthropicProvider

    # Build mock Anthropic SDK stream
    def _make_raw(type_: str, **kwargs: object) -> MagicMock:
        m = MagicMock()
        m.type = type_
        for k, v in kwargs.items():
            setattr(m, k, v)
        return m

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hello world"

    final_usage = MagicMock()
    final_usage.input_tokens = 10
    final_usage.output_tokens = 5
    final_usage.cache_creation_input_tokens = None
    final_usage.cache_read_input_tokens = None
    final_usage.model_dump = lambda: {"input_tokens": 10, "output_tokens": 5}

    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.usage = final_usage

    raw_events = [
        _make_raw("content_block_start", index=0, content_block=MagicMock(type="text")),
        _make_raw(
            "content_block_delta", index=0, delta=MagicMock(type="text_delta", text="Hello world")
        ),
        _make_raw("content_block_stop", index=0),
    ]

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    stream_ctx.current_message_snapshot = MagicMock(content=[text_block])
    stream_ctx.get_final_message = AsyncMock(return_value=final_msg)

    async def _iter():
        for e in raw_events:
            yield e

    stream_ctx.__aiter__ = lambda self: _iter()

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = stream_ctx

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._client = mock_client

    events = []
    async for event in provider.stream(
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        model="claude-opus-4-6",
        max_tokens=1000,
        block_id_prefix="b0_",
    ):
        events.append(event)

    from sebastian.context.usage import TokenUsage

    assert events == [
        TextBlockStart(block_id="b0_0"),
        TextDelta(block_id="b0_0", delta="Hello world"),
        TextBlockStop(block_id="b0_0", text="Hello world"),
        ProviderCallEnd(
            stop_reason="end_turn",
            usage=TokenUsage(
                input_tokens=10,
                output_tokens=5,
                raw={"input_tokens": 10, "output_tokens": 5},
            ),
        ),
    ]


@pytest.mark.asyncio
async def test_openai_compat_provider_streams_text_and_ends() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from sebastian.core.stream_events import (
        ProviderCallEnd,
        TextBlockStart,
        TextBlockStop,
        TextDelta,
    )
    from sebastian.llm.openai_compat import OpenAICompatProvider

    def _chunk(content: str | None = None, finish_reason: str | None = None) -> MagicMock:
        chunk = MagicMock()
        choice = MagicMock()
        choice.finish_reason = finish_reason
        delta = MagicMock()
        delta.content = content
        delta.tool_calls = None
        choice.delta = delta
        chunk.choices = [choice]
        chunk.usage = None
        return chunk

    def _usage_chunk() -> MagicMock:
        chunk = MagicMock()
        chunk.choices = []
        usage = MagicMock()
        usage.prompt_tokens = 8
        usage.completion_tokens = 4
        usage.total_tokens = 12
        usage.completion_tokens_details = None
        usage.model_dump = lambda: {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}
        chunk.usage = usage
        return chunk

    chunks = [
        _chunk(content="Hello"),
        _chunk(content=" world"),
        _chunk(finish_reason="stop"),
        _usage_chunk(),
    ]

    async def _aiter_chunks():
        for c in chunks:
            yield c

    mock_completion = MagicMock()
    mock_completion.__aiter__ = lambda self: _aiter_chunks()

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    provider = OpenAICompatProvider.__new__(OpenAICompatProvider)
    provider._client = mock_client
    provider._thinking_format = None

    events = []
    async for event in provider.stream(
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        model="gpt-4o",
        max_tokens=1000,
        block_id_prefix="b0_",
    ):
        events.append(event)

    from sebastian.context.usage import TokenUsage

    assert events == [
        TextBlockStart(block_id="b0_0"),
        TextDelta(block_id="b0_0", delta="Hello"),
        TextDelta(block_id="b0_0", delta=" world"),
        TextBlockStop(block_id="b0_0", text="Hello world"),
        ProviderCallEnd(
            stop_reason="stop",
            usage=TokenUsage(
                input_tokens=8,
                output_tokens=4,
                total_tokens=12,
                raw={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            ),
        ),
    ]


def test_thinking_block_stop_has_signature_field() -> None:
    from sebastian.core.stream_events import ThinkingBlockStop

    ev = ThinkingBlockStop(block_id="b0_0", thinking="thought", signature="sig_abc")
    assert ev.signature == "sig_abc"

    ev2 = ThinkingBlockStop(block_id="b0_0", thinking="thought")
    assert ev2.signature is None


def test_llm_account_record_has_required_fields() -> None:
    from sebastian.store.models import LLMAccountRecord

    record = LLMAccountRecord(
        name="test",
        catalog_provider_id="anthropic",
        provider_type="anthropic",
        api_key_enc="fake",
    )
    assert record.catalog_provider_id == "anthropic"
    assert record.provider_type == "anthropic"

    record2 = LLMAccountRecord(
        name="test2",
        catalog_provider_id="custom",
        provider_type="openai",
        api_key_enc="fake",
        base_url_override="https://my-llm.example.com",
    )
    assert record2.base_url_override == "https://my-llm.example.com"
