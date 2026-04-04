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
        ) -> AsyncGenerator[LLMStreamEvent, None]:
            return
            yield  # make it an async generator

    p = ConcreteProvider()
    assert hasattr(p, "stream")
