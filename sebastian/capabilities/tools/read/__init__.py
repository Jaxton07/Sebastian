from __future__ import annotations

from pathlib import Path

from sebastian.capabilities.tools import _file_state
from sebastian.capabilities.tools._path_utils import resolve_path
from sebastian.core.tool import tool
from sebastian.core.types import ToolResult
from sebastian.permissions.types import PermissionTier

_DEFAULT_LIMIT = 2000


@tool(
    name="Read",
    description=(
        "Read the contents of a file. Supports optional offset (1-indexed start line) "
        "and limit (number of lines to read). Defaults to first 2000 lines. "
        "Returns content, total_lines, lines_read, and truncated flag."
    ),
    permission_tier=PermissionTier.LOW,
)
async def read(
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> ToolResult:
    path = str(resolve_path(file_path))
    if not Path(path).exists():
        return ToolResult(ok=False, error=f"File not found: {path}")
    if Path(path).is_dir():
        return ToolResult(ok=False, error=f"Path is a directory, not a file: {path}")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start = max(0, (offset - 1) if offset is not None else 0)
        max_lines = limit if limit is not None else _DEFAULT_LIMIT
        end = min(start + max_lines, total_lines)
        selected = lines[start:end]

        _file_state.record_read(path)

        content = "".join(selected)
        empty_hint = (
            f"File exists but is empty (0 lines): {path}"
            if not content and total_lines == 0
            else None
        )

        return ToolResult(
            ok=True,
            output={
                "content": content,
                "total_lines": total_lines,
                "lines_read": len(selected),
                "truncated": (start + max_lines) < total_lines,
            },
            empty_hint=empty_hint,
        )
    except Exception as e:
        return ToolResult(ok=False, error=str(e))
