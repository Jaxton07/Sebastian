from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from sebastian.capabilities.registry import CapabilityRegistry
from sebastian.core.stream_events import (
    LLMStreamEvent,
    ProviderCallEnd,
    TextBlockStop,
    ThinkingBlockStop,
    ToolCallReady,
    ToolResult,
    TurnDone,
)

if TYPE_CHECKING:
    from sebastian.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 20


def _tool_result_content(result: ToolResult) -> str:
    if result.ok:
        return str(result.output)
    return f"Error: {result.error}"


def _validate_injected_tool_result(
    *,
    tool_id: str,
    tool_name: str,
    result: ToolResult | None,
) -> ToolResult:
    if result is None:
        raise RuntimeError(f"Tool call {tool_name} ({tool_id}) requires an injected ToolResult")
    if result.tool_id != tool_id or result.name != tool_name:
        raise RuntimeError(
            f"Injected ToolResult does not match current tool call {tool_name} ({tool_id})"
        )
    return result


class AgentLoop:
    """Core reasoning loop. Drives multi-turn LLM conversation via LLMProvider."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: CapabilityRegistry,
        model: str = "claude-opus-4-6",
        max_tokens: int | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._model = model
        if max_tokens is not None:
            self._max_tokens = max_tokens
        else:
            from sebastian.config import settings
            self._max_tokens = settings.llm_max_tokens

    async def stream(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        task_id: str | None = None,
    ) -> AsyncGenerator[LLMStreamEvent, ToolResult | None]:
        """Yield LLM stream events; accept tool results injected via asend()."""
        working = list(messages)
        tools = self._registry.get_all_tool_specs()
        full_text_parts: list[str] = []

        for iteration in range(MAX_ITERATIONS):
            assistant_content: list[dict[str, Any]] = []
            tool_results_for_next: list[dict[str, Any]] = []
            stop_reason = "end_turn"

            async for event in self._provider.stream(
                system=system_prompt,
                messages=working,
                tools=tools,
                model=self._model,
                max_tokens=self._max_tokens,
                block_id_prefix=f"b{iteration}_",
            ):
                if isinstance(event, ProviderCallEnd):
                    stop_reason = event.stop_reason
                    continue

                if isinstance(event, ThinkingBlockStop):
                    assistant_content.append(
                        {"type": "thinking", "thinking": event.thinking}
                    )
                    yield event

                elif isinstance(event, TextBlockStop):
                    full_text_parts.append(event.text)
                    assistant_content.append({"type": "text", "text": event.text})
                    yield event

                elif isinstance(event, ToolCallReady):
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_id,
                            "name": event.name,
                            "input": event.inputs,
                        }
                    )
                    injected = yield event
                    validated = _validate_injected_tool_result(
                        tool_id=event.tool_id,
                        tool_name=event.name,
                        result=injected,
                    )
                    tool_results_for_next.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": event.tool_id,
                            "content": _tool_result_content(validated),
                        }
                    )

                else:
                    yield event

            working.append({"role": "assistant", "content": assistant_content})

            if stop_reason != "tool_use":
                yield TurnDone(full_text="".join(full_text_parts))
                return

            working.append({"role": "user", "content": tool_results_for_next})

        logger.warning("Reached MAX_ITERATIONS (%d) for task_id=%s", MAX_ITERATIONS, task_id)
        yield TurnDone(full_text="".join(full_text_parts))
