from __future__ import annotations

import base64
import mimetypes

from sebastian.capabilities.tools._path_utils import resolve_path
from sebastian.core.tool import tool
from sebastian.core.tool_context import get_tool_context
from sebastian.core.types import ModelImagePayload, ToolResult
from sebastian.permissions.types import PermissionTier
from sebastian.store.attachments import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_IMAGE_BYTES,
)


@tool(
    name="vision_observe_image",
    description="Observe a local image file with the current multimodal model.",
    permission_tier=PermissionTier.LOW,
    display_name="Look Image",
)
async def vision_observe_image(file_path: str) -> ToolResult:
    ctx = get_tool_context()
    if ctx is None or not ctx.supports_image_input:
        return ToolResult(
            ok=False,
            error=(
                "Current model does not support image input. Do not retry automatically; "
                "ask the user to switch Sebastian to a multimodal model or run this "
                "through Sebastian's normal tool path."
            ),
        )

    path = resolve_path(file_path)
    if not path.exists():
        return ToolResult(
            ok=False,
            error=(
                f"File not found: {path}. Do not retry automatically; "
                "ask the user for an existing image path."
            ),
        )
    if path.is_dir():
        return ToolResult(
            ok=False,
            error=(
                f"Path is a directory, not a file: {path}. Do not retry automatically; "
                "ask the user for an image file path."
            ),
        )

    mime_type = mimetypes.guess_type(path.name)[0] or ""
    if (
        path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS
        or mime_type not in ALLOWED_IMAGE_MIME_TYPES
    ):
        return ToolResult(
            ok=False,
            error=(
                f"Unsupported image type: {path.suffix or mime_type}. "
                "Do not retry automatically; use JPEG, PNG, WebP, or GIF."
            ),
        )

    try:
        size = path.stat().st_size
    except OSError as exc:
        return ToolResult(
            ok=False,
            error=(
                f"Could not inspect image file: {path} ({exc}). "
                "Do not retry automatically; ask the user to check file permissions "
                "or provide another image path."
            ),
        )
    if size > MAX_IMAGE_BYTES:
        return ToolResult(
            ok=False,
            error=(
                f"Image is too large: {size} bytes. Do not retry automatically; "
                f"ask the user for an image under {MAX_IMAGE_BYTES} bytes."
            ),
        )

    try:
        data = path.read_bytes()
    except OSError as exc:
        return ToolResult(
            ok=False,
            error=(
                f"Could not read image file: {path} ({exc}). "
                "Do not retry automatically; ask the user to check file permissions "
                "or provide another image path."
            ),
        )
    data_size = len(data)
    if data_size > MAX_IMAGE_BYTES:
        return ToolResult(
            ok=False,
            error=(
                f"Image is too large: {data_size} bytes. Do not retry automatically; "
                f"ask the user for an image under {MAX_IMAGE_BYTES} bytes."
            ),
        )
    encoded = base64.b64encode(data).decode("ascii")
    filename = path.name
    display = f"已观察图片 {filename}"
    return ToolResult(
        ok=True,
        output={
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": data_size,
            "source": "file_path",
        },
        display=display,
        model_images=[
            ModelImagePayload(media_type=mime_type, data_base64=encoded, filename=filename)
        ],
    )
