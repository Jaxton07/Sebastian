from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    | TurnDone
)
