from __future__ import annotations

from pathlib import Path

import pytest

from sebastian.core.tool_context import _current_tool_ctx
from sebastian.permissions.types import ToolCallContext

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10


@pytest.fixture
def set_image_ctx():
    tokens = []

    def _set(*, supports_image_input: bool = True) -> None:
        ctx = ToolCallContext(
            task_goal="look",
            session_id="s1",
            task_id=None,
            agent_type="sebastian",
            supports_image_input=supports_image_input,
        )
        tokens.append(_current_tool_ctx.set(ctx))

    yield _set
    for token in tokens:
        try:
            _current_tool_ctx.reset(token)
        except ValueError:
            pass


@pytest.mark.asyncio
async def test_vision_observe_image_success_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, set_image_ctx
) -> None:
    set_image_ctx()
    file_path = tmp_path / "photo.png"
    file_path.write_bytes(PNG_BYTES)

    from sebastian.capabilities.tools.vision_observe_image import vision_observe_image

    result = await vision_observe_image(str(file_path))

    assert result.ok is True
    assert result.output["filename"] == "photo.png"
    assert result.output["mime_type"] == "image/png"
    assert result.output["size_bytes"] == len(PNG_BYTES)
    assert result.output["source"] == "file_path"
    assert result.model_images[0].media_type == "image/png"
    assert result.model_images[0].filename == "photo.png"
    assert result.model_images[0].data_base64
    assert "photo.png" in result.display


@pytest.mark.asyncio
async def test_vision_observe_image_requires_image_capable_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, set_image_ctx
) -> None:
    set_image_ctx(supports_image_input=False)
    file_path = tmp_path / "photo.png"
    file_path.write_bytes(PNG_BYTES)

    from sebastian.capabilities.tools.vision_observe_image import vision_observe_image

    result = await vision_observe_image(str(file_path))

    assert result.ok is False
    assert result.error is not None
    assert "does not support image input" in result.error
    assert "Do not retry automatically" in result.error


@pytest.mark.asyncio
async def test_vision_observe_image_rejects_missing_context(tmp_path: Path) -> None:
    token = _current_tool_ctx.set(None)
    file_path = tmp_path / "photo.png"
    file_path.write_bytes(PNG_BYTES)

    try:
        from sebastian.capabilities.tools.vision_observe_image import vision_observe_image

        result = await vision_observe_image(str(file_path))
    finally:
        _current_tool_ctx.reset(token)

    assert result.ok is False
    assert result.error is not None
    assert "does not support image input" in result.error
    assert "Do not retry automatically" in result.error


@pytest.mark.asyncio
async def test_vision_observe_image_rejects_missing_file(set_image_ctx) -> None:
    set_image_ctx()

    from sebastian.capabilities.tools.vision_observe_image import vision_observe_image

    result = await vision_observe_image("/tmp/vision_observe_missing_photo.png")

    assert result.ok is False
    assert result.error is not None
    assert "File not found" in result.error
    assert "Do not retry automatically" in result.error


@pytest.mark.asyncio
async def test_vision_observe_image_rejects_directory(tmp_path: Path, set_image_ctx) -> None:
    set_image_ctx()

    from sebastian.capabilities.tools.vision_observe_image import vision_observe_image

    result = await vision_observe_image(str(tmp_path))

    assert result.ok is False
    assert result.error is not None
    assert "directory" in result.error.lower()
    assert "Do not retry automatically" in result.error


@pytest.mark.asyncio
async def test_vision_observe_image_rejects_unsupported_suffix(
    tmp_path: Path, set_image_ctx
) -> None:
    set_image_ctx()
    file_path = tmp_path / "notes.txt"
    file_path.write_text("not an image", encoding="utf-8")

    from sebastian.capabilities.tools.vision_observe_image import vision_observe_image

    result = await vision_observe_image(str(file_path))

    assert result.ok is False
    assert result.error is not None
    assert "Unsupported image type" in result.error
    assert "Do not retry automatically" in result.error
