---
integrated_to: capabilities/core-tools.md, capabilities/browser-tool.md, core/runtime.md
integrated_at: 2026-05-05
---

# Sebastian 视觉观察 P0 设计

## 背景

Sebastian 现在已经支持用户侧图片附件。用户在聊天里上传图片后，
`session_context.py` 会把附件投影成 Anthropic / OpenAI-compatible 的多模态
content block，模型可以看到这张图。

Sebastian 也已经可以把图片发给用户，例如 `send_file`、
`capture_screenshot_and_send` 和 `browser_capture`。但这些工具走的是
artifact 窄通道：图片会出现在用户聊天界面和 timeline 里，模型侧只收到轻量
metadata，不会看到图片像素。

当前缺口是 Agent 主动观察视觉内容：

- Sebastian 不能主动读取一个本地图片文件并让多模态模型看图。
- 浏览器工具虽然能截图发给用户，但模型不能以视觉形式观察当前页面。
- `Read` 是文本读取工具，不应该承担图片视觉输入职责。

本设计补齐 P0 视觉观察能力，同时保持现有文本读取和用户侧 artifact 语义不变。

## 目标

- 让 Sebastian 能用多模态模型观察本地图片文件。
- 让 Sebastian 能视觉观察当前 managed browser 页面。
- 保持 `Read` 只读文本。
- 保持 `send_file` 和 `browser_capture` 只负责向用户发送 artifact，不偷偷变成模型视觉输入工具。
- 复用现有 provider 图片能力元数据和附件图片校验规则。
- 当前模型不支持图片输入时明确失败。

## 非目标

- 不做 OCR。
- 不做跨 turn 视觉记忆。
- 不做自动图片摘要缓存。
- 不做新的高层视觉 Agent。
- 不做“刚才第二张图”这类多图引用解析。
- 不在每次浏览器操作后自动视觉观察页面。
- 不把 `Read` 扩展成通用二进制读取工具。

## 核心原则

视觉观察不是文件读取，而是一次模型输入操作。

`Read` 回答的是：“这个文件里的 UTF-8 文本内容是什么？”

视觉观察回答的是：“把这些像素交给当前模型，让模型在下一步推理里看见它。”

这两个契约不同，应该保持边界清晰。

## 工具表面

新增两个 Native Tool：

```text
vision_observe_image(file_path: str)
browser_look(full_page: bool = false)
```

按 `sebastian/capabilities/tools/README.md` 的新增工具规范实现：

- `vision_observe_image` 新建目录 `sebastian/capabilities/tools/vision_observe_image/`，
  入口文件为 `__init__.py`，通过 `@tool` 装饰器注册，服务重启后由 `_loader.py`
  自动扫描。
- `browser_look` 属于现有 browser tool surface，应加在
  `sebastian/capabilities/tools/browser/__init__.py`，不另建第二套 browser runtime。
- `vision_observe_image` 必须显式设置 `permission_tier=PermissionTier.LOW` 和 `display_name`。
- `browser_look` 必须显式设置 `permission_tier=PermissionTier.MODEL_DECIDES`、
  `display_name` 和 `review_preflight`。
- 所有工具函数必须是 `async def`，并返回 `sebastian.core.types.ToolResult`。
- 实现完成后必须同步更新 `sebastian/capabilities/tools/README.md`、上级
  `sebastian/capabilities/README.md`，以及受影响的架构 spec。

### `vision_observe_image`

读取一个图片文件，并把它作为 image content block 注入模型侧工具结果。

输入：

- `file_path: str`

校验：

- 路径必须通过 `sebastian.capabilities.tools._path_utils.resolve_path()` 解析。
- 文件不存在或路径是目录时直接失败。
- 支持 AttachmentStore 已支持的图片类型：JPEG、PNG、WebP、GIF。
- 复用 `sebastian.store.attachments` 的图片常量：`ALLOWED_IMAGE_MIME_TYPES`、
  `ALLOWED_IMAGE_EXTENSIONS`、`MAX_IMAGE_BYTES`；不要在工具里硬编码第二套规则。
- 不支持的后缀或 MIME type 必须确定性失败。
- 返回视觉 payload 前必须检查当前 provider 的 `supports_image_input`。

模型侧输出：

- Anthropic：`tool_result.content` 包含短文本 block 和 `image` block，图片 source 使用 base64。
- OpenAI-compatible：当前 chat-completions runtime 的 tool message 是文本通道，因此先追加文本 tool result，再追加一个 synthetic user content block，里面放 `image_url` data URL。

人类/UI 侧输出：

- `ToolResult.output` 只包含 filename、MIME type、size、source kind 等 metadata。
- `ToolResult.display` 使用短句，例如 `已观察图片 photo.png`。
- 该工具不创建 artifact，也不把图片发给用户。

### `browser_look`

截取当前 `browser_open` 打开的页面，并把截图作为 image content block 注入模型侧工具结果。

输入：

- `full_page: bool = false`

校验：

- 必须存在一个由 Sebastian browser tool 打开的当前页面。
- 复用 `browser_observe` 的当前页面归属 / preflight 思路。
- 必须检查当前 provider 的 `supports_image_input`。
- 不改变现有 browser URL、DNS、redirect 和网络安全边界。

行为：

- 通过 `BrowserSessionManager` 截图。
- 默认不上传为 attachment。
- 构造完模型侧视觉 payload 后删除临时截图文件。
- `output` 只返回轻量 metadata：去掉 query/fragment 的 URL、MIME type、byte size、`full_page`。
- P0 不要求返回 title 或图片尺寸。现有 `BrowserScreenshotResult` 只有 `path` / `url`，
  若后续确实需要 title / dimensions，应单独扩展 browser manager 或用 Pillow 读取尺寸。

与现有浏览器工具的关系：

- `browser_observe` 仍是 DOM / 文本 / 可交互元素观察工具。
- `browser_look` 是视觉观察工具。
- `browser_capture` 仍是向用户发送截图 artifact 的工具。

## 运行时抽象

给 `ToolResult` 增加一条模型侧图片通道，不把 base64 塞进普通 `output`。

需要同时覆盖两层 `ToolResult`：

1. `sebastian.core.types.ToolResult`：工具函数实际返回的结果。
2. `sebastian.core.stream_events.ToolResult`：`dispatch_tool_call()` 重新封装后交还
   `AgentLoop` 的 stream event 结果。

概念结构：

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

`stream_events.ToolResult` 也必须携带：

```python
model_content: str | None = None
model_images: list[ModelImagePayload] = field(default_factory=list)
```

`dispatch_tool_call()` 必须从工具层 `ToolResult` 透传 `model_images`，并把
`format_tool_display(result)` 得到的轻量文本写入 `model_content`。模型侧文本使用
`model_content`，不能把 metadata JSON 当作视觉观察描述。

只有 `AgentLoop` 负责把 `model_images` 翻译成不同 provider 的 message block。

Timeline 持久化和 SSE 展示继续使用现有的轻量 `output` / `display` 路径。
`model_images` 是本次工具调用的运行时模型输入，不是用户可见 artifact；不得进入 SSE
`tool.executed` payload、timeline `artifact` 或普通 `output`。

## Provider 能力检查

当前 LLM catalog、resolved provider metadata、LLM binding API 和 Android DTO 已有
`supports_image_input`。用户从 App 上传图片前会读取 binding 能力，后端
`validate_and_write_attachment_turn()` 也会用 `state.llm_registry.get_provider(agent_type)`
兜底校验图片输入能力。

P0 复用这套 resolved binding 能力作为唯一门禁，不新增第二套多模态能力配置。
后端附件兜底必须 fail-closed：如果 `get_provider(agent_type)` 因默认模型缺失、binding
失效、account/model 配置损坏等原因抛 `RuntimeError`，图片附件 turn 不得继续写入，应返回明确
HTTP 错误。

落点：

- `BaseAgent.run_streaming()` 解析 `ResolvedProvider.supports_image_input` 后，沿
  `run_streaming -> _stream_inner -> dispatch_tool_call -> ToolCallContext` 传递。
- vision 工具只读取 `get_tool_context().supports_image_input`。
- 不可用或不支持时，返回 `ToolResult(ok=False, error=...)`，错误信息明确包含
  `Do not retry automatically`。

不要在每个工具里重复调用 `state.llm_registry.get_provider(...)`；provider 能力属于工具执行上下文。

`BaseAgent` 仍支持测试 / 脚本直接注入 provider。该路径不经过 `LLMProviderRegistry`，
因此默认必须 fail-closed。若调用方确实注入多模态 provider，需在构造 `BaseAgent` 时显式传入
`supports_image_input=True`（或等价字段），不能从 provider 对象上隐式猜测能力。

## 数据流

### 本地图片

```text
LLM 调用 vision_observe_image(file_path)
  -> PolicyGate 校验 allowlist / permission
  -> 工具解析并校验图片
  -> 工具返回 metadata + model_images
  -> AgentLoop 按当前 provider 投影 model_images
  -> 下一次 provider call 能看到图片
```

### 浏览器页面

```text
LLM 调用 browser_open(url)
LLM 调用 browser_look(full_page=false)
  -> BrowserSessionManager 截取当前页面
  -> 工具返回 metadata + model_images
  -> AgentLoop 按当前 provider 投影截图
  -> 下一次 provider call 能视觉观察页面
```

## 权限与暴露范围

`vision_observe_image` 是普通只读能力工具，权限设为 `PermissionTier.LOW`。路径参数必须使用
`_path_utils.resolve_path()`，禁止使用 `os.path.abspath()` 或进程 cwd 作为解析基准。若现有
`Read` 允许绝对路径，则保持语义一致，并继续依赖 PolicyGate 的 workspace 边界检查。

`browser_look` 会把当前页面截图交给模型，可能比 DOM 文本暴露更多敏感信息，因此权限设为
`PermissionTier.MODEL_DECIDES`，并复用 `browser_observe` 的 `_browser_observe_preflight`。
它跟随现有 browser tool 的暴露策略：P0 只给 Sebastian 主 Agent，不单独引入第二套 audience 标记。

两个工具都必须受 `allowed_tools` 控制。Sub-Agent 默认不应看到或执行这些工具，除非 manifest
明确配置。

建议显示名：

| 工具名 | display_name |
|--------|--------------|
| `vision_observe_image` | `Look Image` |
| `browser_look` | `Browser Look` |

## 错误处理

确定性失败必须返回 `ToolResult(ok=False, error=...)`，不能用成功 metadata 描述失败。

关键失败场景：

- 文件不存在。
- 路径是目录。
- 图片类型不支持。
- 图片过大。
- 当前模型不支持图片输入。
- Browser manager 不可用。
- 当前没有 browser page。
- 截图失败。

不应自动重试的错误必须包含明确指引。

## 测试策略

后端单元测试：

- `vision_observe_image` 对小 PNG / JPEG 成功，返回 metadata 和一个 model image payload。
- 不支持的文件类型确定性失败。
- 文件不存在和目录路径确定性失败。
- provider 不支持图片输入时，在返回 image payload 前失败。
- `browser_look` 要求当前 browser page 存在。
- manager 截图成功时，`browser_look` 返回 metadata 和一个 model image payload。
- `browser_capture` 行为不变，仍只返回用户侧 artifact。

Agent loop 测试：

- Anthropic 投影会把 `model_images` 转成 tool result content 内的 image block。
- OpenAI-compatible 投影会在下一轮输入中追加 image content block。
- 普通 artifact 结果仍只使用轻量文本，不会变成模型图片输入。

回归测试：

- 对图片文件调用 `Read` 的行为不变：仍按文本解码，不被宣传为视觉工具。
- `send_file` 不把图片 bytes 泄漏进模型上下文。

## 验收标准

- Sebastian 可以调用 `vision_observe_image`，并在多模态模型下回答本地图片相关问题。
- Sebastian 可以调用 `browser_open` 后再调用 `browser_look`，并回答渲染页面的视觉状态问题。
- 非多模态模型 binding 明确失败。
- 不存在 OCR 行为。
- 不存在跨 turn 视觉记忆。
- 现有向用户发送图片和浏览器截图 artifact 的行为保持不变。
