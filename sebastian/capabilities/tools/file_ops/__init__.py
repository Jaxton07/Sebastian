# mypy: disable-error-code=import-untyped
from __future__ import annotations

from pathlib import Path

import aiofiles

from sebastian.core.tool import tool
from sebastian.core.types import ToolResult
from sebastian.permissions.types import PermissionTier


@tool(
    name="file_read",
    description="Read the full contents of a file at the given path.",
    permission_tier=PermissionTier.LOW,
)
async def file_read(path: str) -> ToolResult:
    try:
        async with aiofiles.open(path) as f:
            content = await f.read()
        return ToolResult(ok=True, output={"path": path, "content": content})
    except Exception as e:
        return ToolResult(ok=False, error=str(e))


@tool(
    name="file_write",
    description="Write text content to a file, creating parent directories as needed.",
    permission_tier=PermissionTier.MODEL_DECIDES,
)
async def file_write(path: str, content: str) -> ToolResult:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w") as f:
            await f.write(content)
        return ToolResult(ok=True, output={"path": path, "bytes_written": len(content)})
    except Exception as e:
        return ToolResult(ok=False, error=str(e))
