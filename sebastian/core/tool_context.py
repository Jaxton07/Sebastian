# sebastian/core/tool_context.py
from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sebastian.permissions.types import ToolCallContext

_current_tool_ctx: ContextVar[ToolCallContext | None] = ContextVar("tool_ctx", default=None)


def get_tool_context() -> ToolCallContext | None:
    """Return the ToolCallContext for the currently executing tool, or None."""
    return _current_tool_ctx.get()
