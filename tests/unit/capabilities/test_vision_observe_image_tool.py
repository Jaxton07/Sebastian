from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import sebastian.capabilities.tools.vision_observe_image  # noqa: F401
from sebastian.capabilities.registry import CapabilityRegistry
from sebastian.core.tool import get_tool
from sebastian.core.tool_context import _current_tool_ctx
from sebastian.orchestrator.sebas import Sebastian
from sebastian.permissions.types import ALL_TOOLS, PermissionTier, ToolCallContext

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10


def test_vision_observe_image_registers_metadata() -> None:
    entry = get_tool("vision_observe_image")

    assert entry is not None
    spec = entry[0]
    assert spec.display_name == "Look Image"
    assert spec.permission_tier == PermissionTier.LOW


def test_vision_observe_image_visible_through_sebastian_allowlist() -> None:
    assert "vision_observe_image" in Sebastian.allowed_tools

    registry = CapabilityRegistry()
    no_tools = {spec["name"] for spec in registry.get_callable_specs(None, None)}
    all_tools = {spec["name"] for spec in registry.get_callable_specs(ALL_TOOLS, None)}

    assert "vision_observe_image" not in no_tools
    assert "vision_observe_image" in all_tools


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


@pytest.mark.asyncio
async def test_vision_observe_image_rejects_oversized_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, set_image_ctx
) -> None:
    set_image_ctx()
    file_path = tmp_path / "photo.png"
    file_path.write_bytes(PNG_BYTES)

    import sebastian.capabilities.tools.vision_observe_image as module

    monkeypatch.setattr(module, "MAX_IMAGE_BYTES", len(PNG_BYTES) - 1)

    result = await module.vision_observe_image(str(file_path))

    assert result.ok is False
    assert result.error is not None
    assert "Image is too large" in result.error
    assert str(len(PNG_BYTES) - 1) in result.error
    assert "Do not retry automatically" in result.error


@pytest.mark.asyncio
async def test_vision_observe_image_returns_tool_result_when_stat_fails(
    monkeypatch: pytest.MonkeyPatch, set_image_ctx
) -> None:
    set_image_ctx()

    class StatFailPath:
        name = "photo.png"
        suffix = ".png"

        def __str__(self) -> str:
            return "/images/photo.png"

        def exists(self) -> bool:
            return True

        def is_dir(self) -> bool:
            return False

        def stat(self) -> SimpleNamespace:
            raise PermissionError("stat denied")

    import sebastian.capabilities.tools.vision_observe_image as module

    monkeypatch.setattr(module, "resolve_path", lambda _path: StatFailPath())

    result = await module.vision_observe_image("/images/photo.png")

    assert result.ok is False
    assert result.error is not None
    assert "Could not inspect image file" in result.error
    assert "Do not retry automatically" in result.error


@pytest.mark.asyncio
async def test_vision_observe_image_returns_tool_result_when_read_fails(
    monkeypatch: pytest.MonkeyPatch, set_image_ctx
) -> None:
    set_image_ctx()

    class ReadFailPath:
        name = "photo.png"
        suffix = ".png"

        def __str__(self) -> str:
            return "/images/photo.png"

        def exists(self) -> bool:
            return True

        def is_dir(self) -> bool:
            return False

        def stat(self) -> SimpleNamespace:
            return SimpleNamespace(st_size=len(PNG_BYTES))

        def read_bytes(self) -> bytes:
            raise PermissionError("read denied")

    import sebastian.capabilities.tools.vision_observe_image as module

    monkeypatch.setattr(module, "resolve_path", lambda _path: ReadFailPath())

    result = await module.vision_observe_image("/images/photo.png")

    assert result.ok is False
    assert result.error is not None
    assert "Could not read image file" in result.error
    assert "Do not retry automatically" in result.error
