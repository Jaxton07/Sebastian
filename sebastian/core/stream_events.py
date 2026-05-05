from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sebastian.context.usage import TokenUsage
from sebastian.core.types import ModelImagePayload


@dataclass
class ThinkingBlockStart:
    block_id: str


@dataclass
class ThinkingDelta:
    block_id: str
    delta: str


@dataclass
class ThinkingBlockStop:
    block_id: str
    thinking: str  # full accumulated thinking text for this block
    signature: str | None = None
    duration_ms: int | None = None


@dataclass
class TextBlockStart:
    block_id: str


@dataclass
class TextDelta:
    block_id: str
    delta: str


@dataclass
class TextBlockStop:
    block_id: str
    text: str  # full accumulated text for this block


@dataclass
class ToolCallBlockStart:
    block_id: str
    tool_id: str
    name: str


@dataclass
class ToolCallReady:
    block_id: str
    tool_id: str
    name: str
    inputs: dict[str, Any]


@dataclass
class ToolResult:
    tool_id: str
    name: str
    ok: bool
    output: Any
    error: str | None
    empty_hint: str | None = None
    model_content: str | None = None
    model_images: list[ModelImagePayload] = field(default_factory=list)


@dataclass
class ProviderCallStart:
    index: int  # agent_loop 的 iteration 值，从 0 开始


@dataclass
class ProviderCallEnd:
    stop_reason: str  # "end_turn" | "tool_use" | "max_tokens" | "stop_sequence"
    usage: TokenUsage | None = None


@dataclass
class TurnDone:
    full_text: str


LLMStreamEvent = (
    ThinkingBlockStart
    | ThinkingDelta
    | ThinkingBlockStop
    | TextBlockStart
    | TextDelta
    | TextBlockStop
    | ToolCallBlockStart
    | ToolCallReady
    | ToolResult
    | ProviderCallStart
    | ProviderCallEnd
    | TurnDone
)
