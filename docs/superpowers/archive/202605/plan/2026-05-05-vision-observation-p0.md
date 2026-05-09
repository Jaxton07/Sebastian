# Vision Observation P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Sebastian 能用多模态模型主动观察本地图片和当前浏览器页面截图，同时保持 `Read`、`send_file`、`browser_capture` 的现有语义不变。

**Architecture:** 在 `ToolResult` 增加运行时-only 的 `model_images` 通道，由 `AgentLoop` 按 provider 格式投影成多模态输入。新增独立 `vision_observe_image` 工具读取本地图片；在现有 browser tool surface 增加 `browser_look`，复用 `BrowserSessionManager.capture_screenshot()`。

**Tech Stack:** Python 3.12、Pydantic、Sebastian Native Tools、PolicyGate allowlist、pytest / pytest-asyncio、现有 Playwright browser manager 测试替身。

---

## Files

- Modify: `sebastian/core/types.py`
  - 新增 `ModelImagePayload`，给 `ToolResult` 增加 `model_images`。
- Modify: `sebastian/core/stream_events.py`
  - 给 stream event 层 `ToolResult` 增加 `model_content`、`model_images`，避免 dispatch 重封装丢失视觉 payload。
- Modify: `sebastian/permissions/types.py`
  - 给 `ToolCallContext` 增加 `supports_image_input: bool = False`。
- Modify: `sebastian/core/base_agent.py`
  - 将 `ResolvedProvider.supports_image_input` 从 `run_streaming()` 传到 `_stream_inner()`，再传给 `dispatch_tool_call()`；direct provider injection 路径默认 fail-closed，除非构造器显式传入图片能力。
- Modify: `sebastian/core/stream_helpers.py`
  - 创建 `ToolCallContext` 时写入当前 resolved provider 的 `supports_image_input`；重封装 stream result 时透传 `model_content` / `model_images`。
- Modify: `sebastian/core/agent_loop.py`
  - 将 `ToolResult.model_images` 投影到 Anthropic / OpenAI-compatible 后续输入。
- Modify: `sebastian/gateway/routes/_attachment_helpers.py`
  - 图片附件 turn 写入时，如果 provider 解析失败，后端兜底必须 fail-closed。
- Create: `sebastian/capabilities/tools/vision_observe_image/__init__.py`
  - 新增 `vision_observe_image(file_path: str)` 工具。
- Modify: `sebastian/capabilities/tools/browser/__init__.py`
  - 新增 `browser_look(full_page: bool = False)` 工具。
- Modify: `sebastian/orchestrator/sebas.py`
  - 将 `vision_observe_image`、`browser_look` 加入 Sebastian `allowed_tools`。
- Modify: `sebastian/capabilities/tools/README.md`
  - 同步新增工具目录、修改导航、display_name。
- Modify: `sebastian/capabilities/README.md`
  - 同步 capabilities 工具树。
- Modify: `docs/architecture/spec/capabilities/core-tools.md`
  - 记录 `ToolResult.model_images` 与视觉工具约束。
- Modify: `docs/architecture/spec/capabilities/browser-tool.md`
  - 增补 `browser_look`，明确它不同于 `browser_capture`。
- Modify: `docs/architecture/spec/core/runtime.md`
  - 同步 `stream_events.ToolResult` / AgentLoop 工具结果回灌契约。
- Modify: `docs/architecture/spec/INDEX.md`
  - 如摘要涉及 runtime/tool result 契约，同步更新。
- Test: `tests/unit/capabilities/test_tool_result_content.py`
- Test: `tests/unit/capabilities/test_vision_observe_image_tool.py`
- Test: `tests/unit/capabilities/browser/test_browser_tools.py`
- Test: `tests/unit/identity/test_permission_types.py`
- Test: `tests/integration/test_gateway_attachments.py`

## Constraints

- `vision_observe_image` 为 `permission_tier=PermissionTier.LOW`。
- `browser_look` 为 `permission_tier=PermissionTier.MODEL_DECIDES`，并复用 browser observe preflight。
- 工具函数必须 `async def`，返回 `ToolResult`。
- `vision_observe_image` 的路径必须使用 `_path_utils.resolve_path()`。
- 图片类型和大小限制必须复用 `sebastian.store.attachments` 的 `ALLOWED_IMAGE_MIME_TYPES`、`ALLOWED_IMAGE_EXTENSIONS`、`MAX_IMAGE_BYTES`。
- 不做 OCR。
- 不做跨 turn 视觉记忆。
- 不把 base64 放进普通 `output`、timeline artifact 或 SSE display。
- `send_file` / `browser_capture` 仍只给用户发 artifact，不给模型看像素。
- 用户图片附件后端兜底必须 fail-closed：`llm_registry.get_provider(agent_type)` 失败时不能写入 image attachment turn。

---

### Task 0: Image Attachment Capability Fallback

**Files:**
- Modify: `sebastian/gateway/routes/_attachment_helpers.py`
- Test: `tests/integration/test_gateway_attachments.py`

- [ ] **Step 1: Write failing integration test**

Add a test for image attachment turn creation where the LLM registry cannot resolve the current provider:

```python
def test_image_attachment_turn_fails_when_provider_resolution_fails(client, monkeypatch) -> None:
    http_client, token = client
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: create a real Sebastian session first. The follow-up endpoint
    # resolves the session before entering attachment validation.
    with patch(
        "sebastian.gateway.routes.turns._ensure_llm_ready",
        new_callable=AsyncMock,
    ), patch(
        "sebastian.gateway.state.sebastian.run_streaming",
        new_callable=AsyncMock,
    ):
        create = http_client.post(
            "/api/v1/turns",
            json={"content": "initial"},
            headers=headers,
        )
    assert create.status_code == 200, create.text
    session_id = create.json()["session_id"]

    upload_resp = http_client.post(
        "/api/v1/attachments",
        files={"file": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        data={"kind": "image"},
        headers=headers,
    )
    assert upload_resp.status_code == 201, upload_resp.text
    attachment_id = upload_resp.json()["attachment_id"]

    import sebastian.gateway.state as state

    async def fail_get_provider(agent_type: str):
        raise RuntimeError("no provider configured")

    monkeypatch.setattr(state.llm_registry, "get_provider", fail_get_provider)

    # Patch _ensure_llm_ready to no-op so the request reaches
    # validate_and_write_attachment_turn(); otherwise the route fails before the
    # helper under test. The state.llm_registry.get_provider monkeypatch above
    # must still be active so the helper itself sees the RuntimeError.
    with patch(
        "sebastian.gateway.routes.turns._ensure_llm_ready",
        new_callable=AsyncMock,
    ):
        turn_resp = http_client.post(
            f"/api/v1/sessions/{session_id}/turns",
            json={"content": "看图", "attachment_ids": [attachment_id]},
            headers=headers,
        )

    assert turn_resp.status_code in {400, 503}
    assert "image input" in turn_resp.text or "model" in turn_resp.text
```

Use the existing helper bytes, `AsyncMock`, and session creation pattern in
`tests/integration/test_gateway_attachments.py`; do not invent a second fixture if the file already
has one. The important part is that `_ensure_llm_ready` is patched to no-op while
`state.llm_registry.get_provider()` still fails inside `_attachment_helpers.validate_and_write_attachment_turn()`.

- [ ] **Step 2: Run failing test**

Run:

```bash
pytest tests/integration/test_gateway_attachments.py -q
```

Expected: FAIL because `_attachment_helpers.py` currently catches `RuntimeError`, sets `resolved=None`, and lets the image attachment turn continue.

- [ ] **Step 3: Implement fail-closed backend guard**

In `sebastian/gateway/routes/_attachment_helpers.py`, replace the current `RuntimeError -> resolved=None` logic:

```python
try:
    resolved = await state.llm_registry.get_provider(agent_type)
except RuntimeError as exc:
    raise HTTPException(
        503,
        "current model could not be resolved for image input",
    ) from exc
if not resolved.supports_image_input:
    raise HTTPException(400, "current model does not support image input")
```

Use `400` if the codebase treats invalid binding as client configuration error; use `503` if the route already treats provider unavailability as service unavailable. Pick one and assert that exact status in the test.

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/integration/test_gateway_attachments.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/gateway/routes/_attachment_helpers.py tests/integration/test_gateway_attachments.py
git commit -m "fix(gateway): 图片附件模型能力校验失败关闭"
```

---

### Task 1: Runtime Image Payload Types

**Files:**
- Modify: `sebastian/core/types.py`
- Modify: `sebastian/core/stream_events.py`
- Modify: `sebastian/permissions/types.py`
- Test: `tests/unit/core/test_types.py`
- Test: `tests/unit/core/test_stream_events.py`
- Test: `tests/unit/identity/test_permission_types.py`

- [ ] **Step 1: Write failing tests for defaults**

Add tests:

In `tests/unit/core/test_types.py`:

```python
from sebastian.core.types import ModelImagePayload, ToolResult


def test_tool_result_model_images_defaults_empty() -> None:
    result = ToolResult(ok=True, output={"filename": "photo.png"})
    assert result.model_images == []


def test_model_image_payload_holds_base64_data() -> None:
    payload = ModelImagePayload(media_type="image/png", data_base64="abc", filename="p.png")
    assert payload.media_type == "image/png"
    assert payload.data_base64 == "abc"
    assert payload.filename == "p.png"
```

In `tests/unit/core/test_stream_events.py`:

```python
from sebastian.core.stream_events import ToolResult as StreamToolResult


def test_stream_tool_result_model_images_defaults_empty() -> None:
    result = StreamToolResult(
        tool_id="toolu_1",
        name="vision_observe_image",
        ok=True,
        output={"filename": "photo.png"},
        error=None,
    )
    assert result.model_images == []
    assert result.model_content is None
```

In `tests/unit/identity/test_permission_types.py`:

```python
from sebastian.permissions.types import ToolCallContext


def test_tool_call_context_image_capability_defaults_false() -> None:
    ctx = ToolCallContext(task_goal="goal", session_id="s1", task_id=None)
    assert ctx.supports_image_input is False
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pytest tests/unit/core/test_types.py -q
pytest tests/unit/core/test_stream_events.py -q
pytest tests/unit/identity/test_permission_types.py -q
```

Expected: FAIL because `ModelImagePayload` and/or `model_images` / `model_content` do not exist.

- [ ] **Step 3: Implement minimal types**

In `sebastian/core/types.py`:

```python
class ModelImagePayload(BaseModel):
    media_type: str
    data_base64: str
    filename: str | None = None


class ToolResult(BaseModel):
    ok: bool
    output: Any = None
    error: str | None = None
    empty_hint: str | None = None
    display: str | None = None
    model_images: list[ModelImagePayload] = Field(default_factory=list)
```

In `sebastian/permissions/types.py`, add field to `ToolCallContext`:

```python
supports_image_input: bool = False
```

In `sebastian/core/stream_events.py`, import the payload type and add defaults:

```python
from dataclasses import dataclass, field

from sebastian.core.types import ModelImagePayload


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
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
pytest tests/unit/core/test_types.py -q
pytest tests/unit/core/test_stream_events.py -q
pytest tests/unit/identity/test_permission_types.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/core/types.py sebastian/core/stream_events.py sebastian/permissions/types.py tests/unit/core/test_types.py tests/unit/core/test_stream_events.py tests/unit/identity/test_permission_types.py
git commit -m "feat(core): 增加工具视觉输入运行时载荷"
```

---

### Task 2: Provider Capability In Tool Context

**Files:**
- Modify: `sebastian/core/base_agent.py`
- Modify: `sebastian/core/stream_helpers.py`
- Test: `tests/unit/capabilities/test_tool_result_content.py` or a focused BaseAgent/stream helper test

- [ ] **Step 1: Write failing dispatch-path test**

Add a focused test that exercises the real dispatch path:

1. Register or monkeypatch a fake LOW tool that returns `get_tool_context().supports_image_input`.
2. Call `dispatch_tool_call()` with `supports_image_input=True`.
3. Assert returned `StreamToolResult.output == {"supports": True}`.
4. Call `dispatch_tool_call()` with `supports_image_input=False` and assert `{"supports": False}`.

Sketch:

```python
from sebastian.core.tool_context import get_tool_context


async def fake_tool() -> ToolResult:
    ctx = get_tool_context()
    assert ctx is not None
    return ToolResult(ok=True, output={"supports": ctx.supports_image_input})
```

Expected: `dispatch_tool_call(..., supports_image_input=True)` creates `ToolCallContext.supports_image_input=True`.

- [ ] **Step 2: Write failing BaseAgent propagation tests**

Add a narrow test around `BaseAgent.run_streaming()` / `_stream_inner()` using a fake `llm_registry.get_provider()` returning an object with:

```python
supports_image_input = True
provider = fake_provider
model = "fake"
thinking_effort = None
```

Make the fake provider request the fake tool above and assert the tool result reports `True`.

Add a second test for direct provider injection:

- Directly inject a fake provider without an explicit image capability flag and assert tool context sees `supports_image_input=False`.
- Construct the agent with a new explicit flag, for example `provider_supports_image_input=True`, and assert tool context sees `True`.
- Do not infer image support from arbitrary provider attributes on direct-injected provider objects. The direct-injection path must be explicit.

- [ ] **Step 3: Run failing tests**

Run the narrow test file with `pytest ... -q`.

Expected: FAIL because `supports_image_input` is always default `False` or not wired.

- [ ] **Step 4: Implement capability propagation**

Implement the explicit chain:

In `BaseAgent.run_streaming()`:

```python
supports_image_input_for_tools = bool(self._provider_supports_image_input)
...
resolved = await self._llm_registry.get_provider(self.name)
...
supports_image_input_for_tools = bool(resolved.supports_image_input)
```

Add an optional constructor parameter on `BaseAgent`:

```python
provider_supports_image_input: bool = False
```

Store it as `self._provider_supports_image_input`. This exists for tests/scripts that inject a provider directly. Production runtime should continue using `LLMProviderRegistry` / resolved binding capability, which is also what the LLM binding API and Android attachment capability checks already expose through `supports_image_input`.

Pass it into `_stream_inner(...)`:

```python
supports_image_input=supports_image_input_for_tools,
```

Add `_stream_inner` parameter:

```python
supports_image_input: bool = False,
```

Pass it into `_dispatch_tool_call_fn(...)`:

```python
supports_image_input=supports_image_input,
```

Update `dispatch_tool_call()` signature in `stream_helpers.py` and set:

```python
context = ToolCallContext(
    ...,
    supports_image_input=supports_image_input,
)
```

Do not make individual tools call `state.llm_registry.get_provider(...)`; provider capability belongs to execution context.

- [ ] **Step 5: Verify**

Run:

```bash
pytest tests/unit/identity/test_permission_types.py -q
pytest tests/unit/capabilities/test_tool_result_content.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sebastian/core/base_agent.py sebastian/core/stream_helpers.py <test-file>
git commit -m "feat(core): 向工具上下文透传图片输入能力"
```

---

### Task 3: Dispatch Result Preservation And AgentLoop Projection

**Files:**
- Modify: `sebastian/core/stream_helpers.py`
- Modify: `sebastian/core/agent_loop.py`
- Test: `tests/unit/capabilities/test_tool_result_content.py`

- [ ] **Step 1: Write failing dispatch preservation test**

Add a test for `dispatch_tool_call()`:

- fake tool returns:

```python
ToolResult(
    ok=True,
    output={"filename": "photo.png", "mime_type": "image/png"},
    display="已观察图片 photo.png",
    model_images=[ModelImagePayload(media_type="image/png", data_base64="abc", filename="photo.png")],
)
```

- assert returned stream result has:

```python
assert stream_result.model_content == "已观察图片 photo.png"
assert stream_result.model_images[0].data_base64 == "abc"
```

- assert appended timeline block has:

```python
assert appended_block["model_content"] == "已观察图片 photo.png"
```

- assert published `tool.executed` payload and appended block do **not** contain `"abc"` or `model_images`.

- [ ] **Step 2: Write failing Anthropic projection test**

Add a test that drives `AgentLoop` with a fake Anthropic-format provider that:

1. First stream emits a `ToolCallReady`.
2. Injected stream `ToolResult` contains `model_content="已观察图片 photo.png"` and one `ModelImagePayload`.
3. Second provider call receives `messages[-1]["content"]` with a `tool_result` whose `content` is a list containing text + image blocks.

Expected Anthropic block shape:

```python
{
    "type": "tool_result",
    "tool_use_id": "toolu_1",
    "content": [
        {"type": "text", "text": "已观察图片 photo.png"},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": "abc",
            },
        },
    ],
}
```

- [ ] **Step 3: Write failing OpenAI-compatible projection test**

Add a fake OpenAI-format provider and assert that after a tool result with `model_images`, `working` receives:

- normal `role: "tool"` text result
- an additional `role: "user"` message with content blocks:

```python
[
    {"type": "text", "text": "已观察图片 photo.png"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
]
```

- [ ] **Step 4: Run failing tests**

Run:

```bash
pytest tests/unit/capabilities/test_tool_result_content.py -q
```

Expected: FAIL because dispatch currently drops `model_images`, and `AgentLoop` currently converts every tool result to text only.

- [ ] **Step 5: Implement dispatch preservation**

In `sebastian/core/stream_helpers.py`, when creating `StreamToolResult`, copy:

```python
model_content=display_content,
model_images=list(result.model_images),
```

On exception/failure paths, leave `model_images=[]` and use error text as `model_content`.

Do not add `model_images` to:

- `event_data`
- `record`
- `append_tool_result_block()` payload

`append_tool_result_block()` should continue storing only `model_content` and display/artifact metadata.
Update `_tool_result_model_content()` so persisted history prefers explicit stream model content:

```python
def _tool_result_model_content(result: StreamToolResult, display: str) -> str:
    if result.model_content:
        return result.model_content
    if isinstance(result.output, dict):
        artifact = result.output.get("artifact")
        if isinstance(artifact, dict):
            return _artifact_model_content(artifact, display)
    return _tool_result_content(result)
```

- [ ] **Step 6: Implement projection helpers**

In `sebastian/core/agent_loop.py`, keep `_tool_result_content()` returning lightweight fallback text. Add helpers that prefer `result.model_content`:

```python
def _tool_result_text(result: ToolResult) -> str:
    if result.model_content:
        return result.model_content
    return _tool_result_content(result)


def _anthropic_tool_result_content(result: ToolResult) -> str | list[dict[str, Any]]:
    text = _tool_result_text(result)
    if not result.model_images:
        return text
    blocks: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for image in result.model_images:
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.media_type,
                    "data": image.data_base64,
                },
            }
        )
    return blocks


def _openai_image_user_message(result: ToolResult) -> dict[str, Any] | None:
    if not result.model_images:
        return None
    content: list[dict[str, Any]] = [{"type": "text", "text": _tool_result_text(result)}]
    for image in result.model_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image.media_type};base64,{image.data_base64}",
                },
            }
        )
    return {"role": "user", "content": content}
```

Use `_anthropic_tool_result_content(validated)` for Anthropic `tool_result.content`.

For OpenAI, keep all `role: "tool"` content text-only and collect image user messages in a second list:

```python
tool_results_for_next: list[dict[str, Any]] = []
openai_image_messages_for_next: list[dict[str, Any]] = []
...
image_msg = _openai_image_user_message(validated)
if image_msg is not None:
    openai_image_messages_for_next.append(image_msg)
...
working.extend(tool_results_for_next)
working.extend(openai_image_messages_for_next)
```

Do not interleave `role: "user"` image messages between individual `role: "tool"` results. OpenAI chat-completions requires all tool call responses for the assistant's tool calls to appear before the next user message.

- [ ] **Step 7: Preserve artifact behavior**

Ensure `_tool_result_content()` artifact handling remains unchanged:

```python
if isinstance(output, dict):
    artifact = output.get("artifact")
    if isinstance(artifact, dict):
        return _artifact_tool_result_content(artifact)
```

- [ ] **Step 8: Verify**

Run:

```bash
pytest tests/unit/capabilities/test_tool_result_content.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add sebastian/core/stream_helpers.py sebastian/core/agent_loop.py tests/unit/capabilities/test_tool_result_content.py
git commit -m "feat(core): 支持工具结果注入图片输入"
```

---

### Task 4: `vision_observe_image` Tool

**Files:**
- Create: `sebastian/capabilities/tools/vision_observe_image/__init__.py`
- Test: `tests/unit/capabilities/test_vision_observe_image_tool.py`

- [ ] **Step 1: Write failing tests**

Create tests covering:

```python
async def test_vision_observe_image_success_png(tmp_path, monkeypatch) -> None: ...
async def test_vision_observe_image_requires_image_capable_model(tmp_path, monkeypatch) -> None: ...
async def test_vision_observe_image_rejects_missing_file() -> None: ...
async def test_vision_observe_image_rejects_directory(tmp_path) -> None: ...
async def test_vision_observe_image_rejects_unsupported_suffix(tmp_path) -> None: ...
```

Use `sebastian.core.tool_context._current_tool_ctx.set(...)` with:

```python
ToolCallContext(
    task_goal="look",
    session_id="s1",
    task_id=None,
    agent_type="sebastian",
    supports_image_input=True,
)
```

For a valid PNG, write minimal bytes or use Pillow if already imported in nearby tests. Expected:

```python
assert result.ok is True
assert result.output["filename"] == "photo.png"
assert result.output["mime_type"] == "image/png"
assert result.model_images[0].media_type == "image/png"
assert result.model_images[0].data_base64
assert "photo.png" in result.display
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pytest tests/unit/capabilities/test_vision_observe_image_tool.py -q
```

Expected: FAIL because the module/tool does not exist.

- [ ] **Step 3: Implement tool**

Create `sebastian/capabilities/tools/vision_observe_image/__init__.py`:

```python
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
                "ask the user to switch Sebastian to a multimodal model or run this through Sebastian's normal tool path."
            ),
        )

    path = resolve_path(file_path)
    if not path.exists():
        return ToolResult(
            ok=False,
            error=f"File not found: {path}. Do not retry automatically; ask the user for an existing image path.",
        )
    if path.is_dir():
        return ToolResult(
            ok=False,
            error=f"Path is a directory, not a file: {path}. Do not retry automatically; ask the user for an image file path.",
        )

    mime_type = mimetypes.guess_type(path.name)[0] or ""
    if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS or mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        return ToolResult(
            ok=False,
            error=f"Unsupported image type: {path.suffix or mime_type}. Do not retry automatically; use JPEG, PNG, WebP, or GIF.",
        )

    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        return ToolResult(
            ok=False,
            error=f"Image is too large: {size} bytes. Do not retry automatically; ask the user for an image under {MAX_IMAGE_BYTES} bytes.",
        )

    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    filename = path.name
    display = f"已观察图片 {filename}"
    return ToolResult(
        ok=True,
        output={
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size,
            "source": "file_path",
        },
        display=display,
        model_images=[
            ModelImagePayload(media_type=mime_type, data_base64=encoded, filename=filename)
        ],
    )
```

If tests show `resolve_path()` returns `str` instead of `Path`, wrap with `Path(resolve_path(...))`.

- [ ] **Step 4: Verify tests**

Run:

```bash
pytest tests/unit/capabilities/test_vision_observe_image_tool.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/capabilities/tools/vision_observe_image/__init__.py tests/unit/capabilities/test_vision_observe_image_tool.py
git commit -m "feat(capabilities): 新增图片视觉观察工具"
```

---

### Task 5: `browser_look` Tool

**Files:**
- Modify: `sebastian/capabilities/tools/browser/__init__.py`
- Test: `tests/unit/capabilities/browser/test_browser_tools.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
async def test_browser_look_requires_image_capable_model(monkeypatch) -> None: ...
async def test_browser_look_requires_browser_manager(monkeypatch) -> None: ...
async def test_browser_look_returns_model_image(monkeypatch, tmp_path) -> None: ...
async def test_browser_look_deletes_temp_file_on_capture_read_failure(monkeypatch, tmp_path) -> None: ...
async def test_browser_look_uses_observe_preflight(monkeypatch) -> None: ...
async def test_browser_look_output_has_no_artifact(monkeypatch, tmp_path) -> None: ...
async def test_browser_capture_has_no_model_images(monkeypatch, tmp_path) -> None: ...
```

Use a fake manager:

```python
class FakeCapture:
    path = tmp_path / "page.png"
    url = "https://example.com/path?secret=1"


class FakeManager:
    async def capture_screenshot(self, *, full_page: bool) -> FakeCapture:
        FakeCapture.path.write_bytes(PNG_BYTES)
        return FakeCapture()
```

Set `ToolCallContext(..., supports_image_input=True)`.

Expected success:

```python
assert result.ok is True
assert result.output["mime_type"] == "image/png"
assert result.output["url"] == "https://example.com/path"
assert result.model_images[0].media_type == "image/png"
assert not (tmp_path / "page.png").exists()
```

Failure cleanup test should make `capture_screenshot()` create the file and then force `Path.read_bytes()` or base64 construction to fail; assert the temp file is still deleted.

Artifact regression tests must assert:

```python
assert "artifact" not in result.output
assert result.model_images

capture_result = await browser_capture()
assert capture_result.model_images == []
assert "artifact" in capture_result.output
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pytest tests/unit/capabilities/browser/test_browser_tools.py -q
```

Expected: FAIL because `browser_look` does not exist.

- [ ] **Step 3: Implement `browser_look`**

In `sebastian/capabilities/tools/browser/__init__.py`, add imports:

```python
import base64
from contextlib import suppress
from sebastian.core.tool_context import get_tool_context
from sebastian.core.types import ModelImagePayload, ToolResult
```

Add tool near `browser_capture`:

```python
@tool(
    name="browser_look",
    description="Visually observe the current browser_open page with the current multimodal model.",
    permission_tier=PermissionTier.MODEL_DECIDES,
    display_name="Browser Look",
    review_preflight=lambda inputs, context: _browser_observe_preflight(inputs, context),
)
async def browser_look(full_page: bool = False) -> ToolResult:
    ctx = get_tool_context()
    if ctx is None or not ctx.supports_image_input:
        return ToolResult(
            ok=False,
            error=(
                "Current model does not support image input. Do not retry automatically; "
                "ask the user to switch Sebastian to a multimodal model or run this through Sebastian's normal tool path."
            ),
        )
    manager = _browser_manager()
    if manager is None:
        return ToolResult(ok=False, error=_BROWSER_UNAVAILABLE)
    path: Path | None = None
    try:
        metadata = await manager.current_page_metadata()
        if metadata is None or not bool(getattr(metadata, "opened_by_browser_tool", False)):
            return ToolResult(ok=False, error=_NO_BROWSER_PAGE)
        capture = await _maybe_await(manager.capture_screenshot(full_page=full_page))
        path = Path(capture.path)
        data = path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        url = _sanitize_url(str(getattr(capture, "url", "") or ""))
        display = "已视觉观察当前浏览器页面"
        return ToolResult(
            ok=True,
            output={
                "url": url,
                "mime_type": "image/png",
                "size_bytes": len(data),
                "full_page": full_page,
            },
            display=display,
            model_images=[
                ModelImagePayload(
                    media_type="image/png",
                    data_base64=encoded,
                    filename=path.name,
                )
            ],
        )
    except RuntimeError as exc:
        if "No browser-tool-owned page" in str(exc):
            return ToolResult(ok=False, error=_NO_BROWSER_PAGE)
        return ToolResult(
            ok=False,
            error=(
                "Browser visual observation failed. Do not retry automatically; "
                "tell the user the current page could not be visually inspected."
            ),
        )
    except Exception:  # noqa: BLE001
        return ToolResult(
            ok=False,
            error=(
                "Browser visual observation failed. Do not retry automatically; "
                "tell the user the current page could not be visually inspected."
            ),
        )
    finally:
        if path is not None:
            with suppress(OSError):
                path.unlink()
```

- [ ] **Step 4: Add Sebastian allowlist**

In `sebastian/orchestrator/sebas.py`, add:

```python
"browser_look",
"vision_observe_image",
```

near the existing browser / file read tools.

- [ ] **Step 5: Verify tests**

Run:

```bash
pytest tests/unit/capabilities/browser/test_browser_tools.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sebastian/capabilities/tools/browser/__init__.py sebastian/orchestrator/sebas.py tests/unit/capabilities/browser/test_browser_tools.py
git commit -m "feat(capabilities): 新增浏览器视觉观察工具"
```

---

### Task 6: Tool Registration, Docs, And Regression

**Files:**
- Modify: `sebastian/capabilities/tools/README.md`
- Modify: `sebastian/capabilities/README.md`
- Modify: `sebastian/core/README.md`
- Modify: `docs/architecture/spec/capabilities/core-tools.md`
- Modify: `docs/architecture/spec/capabilities/browser-tool.md`
- Modify: `docs/architecture/spec/core/runtime.md`
- Modify: `docs/architecture/spec/INDEX.md`
- Modify: `docs/superpowers/specs/2026-05-05-vision-observation-p0-design.md`
- Test: `tests/unit/capabilities/test_tools_read.py`

- [ ] **Step 1: Update README tool tree**

In `sebastian/capabilities/tools/README.md`, add:

```text
├── vision_observe_image/    # 本地图片视觉观察工具（permission_tier: LOW）
│   └── __init__.py          # @tool: vision_observe_image
```

Update browser line:

```text
│   ├── __init__.py          # @tool: browser_open / observe / act / capture / downloads / look
```

Add modification navigation entries for `vision_observe_image` and `browser_look`.

- [ ] **Step 2: Update capability overview**

In `sebastian/capabilities/README.md`, add `vision_observe_image` to the tools tree and update the browser tool note to include visual observation.

- [ ] **Step 3: Update core README**

In `sebastian/core/README.md`, update the ToolResult/AgentLoop note to mention:

```text
model_images 是运行时-only 模型输入通道，不进入普通 output / timeline artifact。
```

- [ ] **Step 4: Update architecture specs**

Update:

- `docs/architecture/spec/capabilities/core-tools.md`
- `docs/architecture/spec/capabilities/browser-tool.md`
- `docs/architecture/spec/core/runtime.md`
- `docs/architecture/spec/INDEX.md`

Record:

- `ToolResult.model_images`
- `stream_events.ToolResult.model_content` / `model_images`
- `dispatch_tool_call()` must preserve model images but keep SSE/timeline free of base64
- `vision_observe_image`
- `browser_look`
- `vision_observe_image` is `PermissionTier.LOW`
- `browser_look` is `PermissionTier.MODEL_DECIDES` and uses browser observe preflight
- no OCR
- no cross-turn visual memory
- `browser_capture` remains user-facing artifact only

- [ ] **Step 5: Add Read regression test**

In `tests/unit/capabilities/test_tools_read.py`, add a test using bytes that are invalid UTF-8 but saved with an image extension:

```python
async def test_read_image_file_remains_text_decode_tool(tmp_path) -> None:
    path = tmp_path / "photo.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")

    result = await read(str(path), limit=5)

    assert result.ok is True
    assert result.model_images == []
    assert isinstance(result.output, dict)
    assert "content" in result.output
```

This asserts `Read` still uses text decoding with replacement behavior and does not become a vision tool.

- [ ] **Step 6: Update design spec integration metadata only if appropriate**

Do not mark the design spec as integrated until implementation is complete. If implementation is complete in this branch, add frontmatter matching existing integrated specs:

```yaml
---
integrated_to: capabilities/core-tools.md, capabilities/browser-tool.md
integrated_at: 2026-05-05
---
```

- [ ] **Step 7: Run targeted backend tests**

Run:

```bash
pytest tests/unit/identity/test_permission_types.py -q
pytest tests/unit/capabilities/test_tool_result_content.py -q
pytest tests/unit/capabilities/test_vision_observe_image_tool.py -q
pytest tests/unit/capabilities/browser/test_browser_tools.py -q
pytest tests/unit/capabilities/test_send_file_tool.py -q
pytest tests/unit/capabilities/test_tools_read.py -q
pytest tests/integration/test_gateway_attachments.py -q
```

Expected: all PASS.

- [ ] **Step 8: Run formatting/lint**

Run:

```bash
ruff check sebastian/ tests/
ruff format sebastian/ tests/
```

Expected: check PASS before format; if format changes files, rerun `ruff check`.

- [ ] **Step 9: Rebuild graphify code graph**

Because code files changed, run:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: command exits 0.

- [ ] **Step 10: Commit docs and final verification**

```bash
git add sebastian/capabilities/tools/README.md sebastian/capabilities/README.md sebastian/core/README.md docs/architecture/spec/capabilities/core-tools.md docs/architecture/spec/capabilities/browser-tool.md docs/architecture/spec/core/runtime.md docs/architecture/spec/INDEX.md docs/superpowers/specs/2026-05-05-vision-observation-p0-design.md docs/superpowers/plans/2026-05-05-vision-observation-p0.md
git commit -m "docs(capabilities): 补充视觉观察工具设计与计划"
```

---

## Final Verification

Run:

```bash
pytest tests/unit/core/test_types.py tests/unit/core/test_stream_events.py tests/unit/identity/test_permission_types.py tests/unit/capabilities/test_tool_result_content.py tests/unit/capabilities/test_vision_observe_image_tool.py tests/unit/capabilities/browser/test_browser_tools.py tests/unit/capabilities/test_send_file_tool.py tests/unit/capabilities/test_tools_read.py tests/integration/test_gateway_attachments.py -q
ruff check sebastian/ tests/
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected:

- all selected pytest tests PASS
- ruff check PASS
- graphify rebuild exits 0

## Handoff Notes

- Do not implement OCR.
- Do not persist `model_images` to timeline or artifact payloads.
- Persisted `tool_result.model_content` for visual tools must use `StreamToolResult.model_content` / display text, not metadata JSON.
- Do not add `vision_observe_image` to sub-agent manifests by default.
- Keep `browser_capture` behavior unchanged.
- If OpenAI-compatible projection conflicts with a specific provider, fail fast in tests and update the provider-specific projection explicitly rather than silently dropping images.
