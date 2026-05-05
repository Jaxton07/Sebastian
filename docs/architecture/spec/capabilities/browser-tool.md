---
version: "1.1"
last_updated: 2026-05-05
status: implemented
---

# Sebastian Browser Tool 设计

*← [Capabilities 索引](INDEX.md) · [Spec 根索引](../INDEX.md)*

---

## 1. 概述

Sebastian 内置 Browser Tool 为主管家提供一组基于 Playwright Chromium 的浏览器工具，用于打开网页、观察页面、视觉观察当前页面、执行低层交互、截图发送和发送下载文件。

设计目标：

- 在无物理显示器的 Ubuntu 部署上默认以 headless Chromium 运行。
- 使用 Playwright persistent context 保存 cookie 和 local storage，降低重复登录成本。
- 工具调用必须经过 Sebastian 的工具注册、`PolicyGate`、事件日志、artifact 发送链路和 Agent 白名单。
- 浏览器 profile 可能包含主人登录态，v1 只暴露给 Sebastian 主 Agent，不给 Aide、Forge 或扩展 Sub-Agent。
- URL、DNS、重定向和子资源请求必须在应用层校验之外有连接时硬边界，避免 DNS rebinding 绕过。

不在 v1 范围内：

- 不提供高层 `browser_task` mini-agent。
- 不公开多 tab / `page_id` API。
- `browser_capture` 不把截图像素、OCR 或图片 bytes 回灌进 LLM 上下文；模型视觉观察必须显式使用 `browser_look`。
- `browser_look` 不做 OCR，不建立跨 turn 视觉记忆。
- 不提供清空浏览器数据 UI / tool。
- 不支持上传、PDF 导出、网络日志检查或浏览器 fingerprint 配置。
- 不向 guest/family 身份暴露共享浏览器 profile；多用户浏览器 profile 需等身份系统进入 tool context 后再设计。

---

## 2. 代码结构

Browser Tool 作为 Native Tool 子包实现：

```text
sebastian/capabilities/tools/browser/
  __init__.py     # @tool: browser_open / observe / act / capture / downloads / look
  artifacts.py   # 浏览器截图与下载 artifact 上传
  downloads.py   # 下载列表与发送 helper
  manager.py     # BrowserSessionManager：Playwright context / page / downloads / screenshots
  network.py     # BrowserDNSResolver：system / DoH / auto DNS 校验
  observe.py     # 页面文本与交互元素观察，敏感表单脱敏
  proxy.py       # FilteringProxy：连接时 egress 边界
  safety.py      # URL parse、hostname normalize、IP 分类阻断
```

> **实现差异**：原始设计稿将安全层命名为 `BrowserSafetyGuard` / `BrowserNetworkGuard`。当前代码没有这两个类名，而是由 `safety.py::validate_public_http_url()`、`network.py::BrowserDNSResolver`、`proxy.py::FilteringProxy` 分担 URL、DNS 与连接时拦截职责。

`BrowserSessionManager` 由 `sebastian.gateway.app.lifespan()` 创建并挂到 `sebastian.gateway.state.browser_manager`。Gateway shutdown 时会在 DB engine dispose 前调用 `browser_manager.aclose()`，关闭 page、context、Playwright driver、过滤代理和下载任务。

---

## 3. 工具暴露与白名单

浏览器工具全局注册，但只加入 `sebastian/orchestrator/sebas.py::Sebastian.allowed_tools`：

```text
browser_open
browser_observe
browser_act
browser_capture
browser_downloads
browser_look
```

`allowed_tools` 是唯一的工具可见性与执行边界：

- `allowed_tools=None` / `[]` 表示不允许能力工具。
- 只有显式 `ALL_TOOLS` sentinel 表示全量工具。
- Sub-Agent manifest 省略 `allowed_tools` 时解析为协议工具 only，不继承全量能力工具。
- `PolicyGate.call()` 在执行前校验工具名是否存在于有效白名单。

相关单测覆盖：

- `tests/unit/capabilities/browser/test_browser_tools.py`
- `tests/unit/identity/test_policy_gate.py`
- `tests/unit/agents/test_agent_loader.py`

---

## 4. Tool Surface

### 4.1 `browser_open(url: str)`

权限：`PermissionTier.MODEL_DECIDES`

行为：

1. 通过 `validate_public_http_url()` 校验用户输入 URL。
2. 通过 `BrowserDNSResolver.resolve_public()` 校验主导航 host。
3. 懒启动 Playwright persistent context。
4. 使用本地 `FilteringProxy` 作为 Chromium 代理。
5. 导航后重新校验 final URL 与 final host。

返回给模型的轻量 output：

```json
{
  "url": "https://example.com/",
  "title": "Example",
  "status": "opened"
}
```

> **实现差异**：原始设计稿写有 short page summary。当前实现不在 `browser_open` 返回页面摘要，页面理解统一由 `browser_observe` 完成。

### 4.2 `browser_observe(max_chars: int = 4000)`

权限：`PermissionTier.MODEL_DECIDES`

读取当前由 `browser_open` 打开的页面，返回：

- `url`
- `title`
- `text`
- `interactive_summary`
- `truncated`

隐私规则：

- 不返回 password / hidden input value。
- `textarea` 内容不作为交互摘要回显。
- 表单控件优先返回 label、placeholder、name、id、title 等元信息。
- URL 会去掉 query 与 fragment 后再进入 review input。

`browser_observe` 带 `review_preflight` hook。`PolicyGate` 调用 reviewer 前会先取 sanitized metadata：

```json
{
  "max_chars": 500,
  "current_url": "https://example.com/account",
  "title": "Account",
  "opened_by_browser_tool": true
}
```

如果没有当前页面，或页面不是 browser tool session 打开的，preflight 直接阻断，不把不完整上下文交给 reviewer。

### 4.3 `browser_act(action, target=None, value=None)`

权限：`PermissionTier.MODEL_DECIDES`

支持的 action：

```text
click
type
press
select
wait_for_text
wait_for_selector
back
forward
reload
```

运行时会校验 action 枚举、必需参数和目标唯一性。`click/type/press/select/wait_for_selector` 主要使用 Playwright selector；`wait_for_text` 使用 `page.get_by_text(target)`。

> **实现差异**：原始设计稿提到 target 可为 CSS selector 或 visible text / role-oriented locator shorthand。当前 v1 没有完整 shorthand 解析层；除 `wait_for_text` 外，target 应按 Playwright selector 使用。

高影响操作在工具内部硬阻断，而不是只靠 prompt：

- 密码、token、secret、API key、credential 等字段。
- payment / checkout / purchase / billing 等支付语义。
- account settings、delete、transfer、profile 等可能修改账户或高影响状态的语义。
- submit control 或带敏感字段的 form。

### 4.4 `browser_capture(display_name: str | None = None)`

权限：`PermissionTier.MODEL_DECIDES`

截取当前 browser tool 页面，写入 `settings.browser_screenshots_dir`，通过 attachment/artifact 路径发送给用户，并在发送后删除临时 PNG。

模型侧 tool result 只包含轻量 artifact metadata，不包含图片 bytes 或 OCR 文本：

```json
{
  "artifact": {
    "kind": "image",
    "attachment_id": "...",
    "filename": "...png",
    "mime_type": "image/png",
    "size_bytes": 12345,
    "download_url": "/api/v1/attachments/...",
    "thumbnail_url": "/api/v1/attachments/.../thumbnail"
  }
}
```

### 4.5 `browser_look(full_page: bool = false)`

权限：`PermissionTier.MODEL_DECIDES`

`browser_look` 截取当前由 `browser_open` 打开的页面，并把截图作为 runtime-only `model_images` 交给下一轮模型请求。它是模型视觉观察工具，不上传 attachment，不创建 timeline artifact。

执行边界：

- 通过 `review_preflight` 获取当前页面 metadata，必须证明页面由 browser tool 打开；没有页面或页面非 browser-owned 时直接阻断。
- 工具执行时再次检查当前页面归属，避免 reviewer 后页面状态变化。
- 使用 `ToolCallContext.supports_image_input` 做 provider 能力门禁；非多模态模型 fail closed。
- 截图 bytes 受 AttachmentStore 图片大小上限约束，超过上限确定性失败。
- 成功后删除临时截图文件。

返回给模型的轻量文本来自 `display` / `model_content`；图片 bytes 只存在于 `model_images`，由 `AgentLoop` 按 provider 投影成多模态输入。SSE、timeline、artifact payload 不包含 base64。

与 `browser_capture` 的区别：

- `browser_capture`：向用户发送截图 artifact，模型只收到轻量 artifact metadata。
- `browser_look`：让模型观察当前页面截图，不上传 artifact，不向用户发送图片。

P0 明确不做 OCR，也不保存跨 turn 视觉记忆。

### 4.6 `browser_downloads(action="list", filename=None)`

权限：`PermissionTier.MODEL_DECIDES`

`action="list"` 返回 downloads manifest 中的文件列表：

```json
{
  "downloads": [
    {
      "filename": "report.pdf",
      "mime": "application/pdf",
      "size": 1234,
      "mtime": 1710000000.0,
      "original": "report.pdf",
      "source_url": "https://example.com/report",
      "created_at": "..."
    }
  ]
}
```

`action="send"` 要求 `filename` 来自列表，并通过 `AttachmentStore` 以 `kind="download"` 发送。

下载安全：

- Playwright `accept_downloads=True`，下载固定落到 `settings.browser_downloads_dir`。
- `save_download()` 使用站点建议文件名生成安全本地 filename，不接受站点提供路径。
- `resolve_download()` 要求 filename 是 plain filename，且 resolve 后仍在 downloads 目录内。

---

## 5. Session 与存储

默认运行参数：

```text
headless = true
browser = chromium
viewport = 1280x900
timeout_ms = 30000
```

数据目录：

```text
~/.sebastian/data/browser/profile/
~/.sebastian/data/browser/downloads/
~/.sebastian/data/browser/screenshots/
```

配置项：

```text
SEBASTIAN_BROWSER_HEADLESS=true
SEBASTIAN_BROWSER_VIEWPORT=1280x900
SEBASTIAN_BROWSER_TIMEOUT_MS=30000
SEBASTIAN_BROWSER_DNS_MODE=auto
SEBASTIAN_BROWSER_DOH_ENDPOINT=https://dns.alidns.com/resolve
SEBASTIAN_BROWSER_DOH_TIMEOUT_MS=5000
SEBASTIAN_BROWSER_UPSTREAM_PROXY=
```

这些字段定义在 `sebastian/config/__init__.py::Settings`，并写入 `.env.example`、`sebastian/config/README.md` 与安装/服务环境模板。

并发模型：

- `_startup_lock`：避免并发启动多个 Playwright context。
- `_operation_lock`：串行化导航、观察、操作、截图。
- `_navigation_lock`：保护导航与 final URL 校验。
- `_download_lock`：保护下载 manifest 写入。

---

## 6. URL、DNS 与网络安全

`safety.py` 使用结构化 URL parser，不做字符串前缀判断。默认只允许 `http` / `https`，并阻断：

- `file://`
- `chrome://`
- `about:`
- `data:`
- `javascript:`
- username/password authority
- localhost / loopback
- private / link-local / multicast / unspecified / reserved IP
- cloud metadata 地址 `169.254.169.254`

URL 校验点：

1. `browser_open` 导航前校验用户输入 URL。
2. DNS 解析后校验所有 A / AAAA answer。
3. 导航后校验 final URL 与 final host。
4. `browser_act` 可能触发导航的 action 后再次校验页面 URL。
5. `FilteringProxy` 在连接时校验 Chromium 发起的主请求和子资源请求。

DNS 策略：

- `system`：只用系统 DNS。
- `doh`：只用 DoH。
- `auto`：系统 DNS 优先；当系统答案全是 `198.18.0.0/15` Fake-IP 时 fallback 到 DoH。

带显式 upstream HTTP proxy 时，Sebastian 的本地过滤代理仍是 Chromium 唯一代理。过滤代理校验允许后，再把请求转发到用户配置的 upstream proxy。

> **实现增强**：当前代码已实现本地 `FilteringProxy` 作为连接时硬边界。`BrowserSessionManager._ensure_context()` 强制通过 proxy 启动 Chromium，并在 proxy 启动失败或配置缺失时 fail closed，不回退直连。

---

## 7. Artifact 与下载链路

Browser screenshot 与 downloads 复用 attachment/artifact 窄通道：

- `AttachmentStore.upload_bytes()` 支持 `kind="download"`。
- download MIME allowlist 支持 PDF、ZIP、XLSX、DOCX 与 `application/octet-stream`。
- download 大小上限为 `MAX_DOWNLOAD_BYTES = 50 MiB`。
- `/api/v1/attachments/{id}` 以 `FileResponse` 供应下载。
- SSE / timeline payload 透传 `artifact.kind`、`download_url`、filename、MIME type、size。
- Android 原生客户端将 `kind="download"` 渲染为 `FileBlock`。

`browser_look` 不走此 artifact 链路。它只在工具执行期间把截图 bytes 封装到 `model_images`，随后由运行时投影给模型，并保持 SSE / timeline 不含 base64。

相关测试：

- `tests/unit/store/test_attachments.py`
- `tests/integration/test_gateway_attachments.py`
- `tests/unit/capabilities/browser/test_browser_downloads.py`
- `ui/mobile-android/app/src/test/java/com/sebastian/android/data/remote/dto/TimelineMapperTest.kt`
- `ui/mobile-android/app/src/test/java/com/sebastian/android/viewmodel/ChatViewModelTest.kt`

---

## 8. 失败行为

浏览器工具失败必须返回 `ToolResult(ok=False, error=...)`，并对不应自动重试的错误包含 `Do not retry automatically`。

关键错误：

- Browser manager 不存在：提示当前 runtime 不可用。
- Chromium 未安装：提示 `python -m playwright install chromium`。
- Ubuntu/browser 系统依赖缺失：提示 `python -m playwright install-deps chromium`。
- URL / DNS / proxy 被阻断：说明阻断类别。
- target 缺失或歧义：提示先 observe 并选择更具体 target。
- 下载路径逃逸或 filename 不在列表中：拒绝并要求先 list。
- `browser_look` 当前模型不支持图片输入、当前页面非 browser-owned 或截图超过图片大小上限：确定性失败。

---

## 9. 测试策略

后端单元测试覆盖：

- browser tools 注册元数据、权限档位与 Sebastian-only 可见性。
- `allowed_tools=None` 无法执行 browser tools；`ALL_TOOLS` 是唯一 unrestricted sentinel。
- `browser_observe` preflight 注入 sanitized URL/title，并阻断无页面/非 browser-owned 页面。
- `browser_look` 使用视觉 preflight / 当前页面归属检查，返回 `model_images`，且不上传 artifact。
- `browser_capture` 仍只产生用户侧 artifact，不返回 `model_images`。
- `browser_act` action 枚举、敏感 credential / high-impact target 阻断。
- URL guard、DNS resolver、Fake-IP、DoH、proxy 连接时阻断。
- manager persistent context、proxy fail closed、final URL redirect 校验、shutdown 清理顺序。
- 下载目录 traversal 阻断、download artifact 上传、截图 artifact 上传后临时文件清理。

可选真实 Playwright 集成测试应继续 gated 在环境变量之后，例如：

```text
SEBASTIAN_RUN_PLAYWRIGHT_TESTS=1
```

本地 HTTP server 测试需显式使用 test-only guard override，因为产品默认阻断 localhost。

---

## 10. 验收标准

- Sebastian 能看到并执行六个 browser tools；Sub-Agent 默认看不到也不能执行。
- 当前单 owner 认证模型下，browser tools 只能通过 authenticated Sebastian owner turn path 触达。
- headless Ubuntu 部署能打开网页并截图，不依赖物理显示器。
- Browser profile、downloads 和 screenshots 目录位于 Sebastian data dir 下。
- Gateway shutdown 关闭 Playwright context/browser/driver 与 filtering proxy，不留下孤儿 Chromium 进程。
- URL 协议、DNS、redirect、子资源请求和 action 后导航均被安全校验。
- DNS rebinding 与子资源请求不能绕过规则，因为本地 filtering proxy 在连接时阻断 forbidden destination IP。
- 高影响浏览器动作在 v1 内部硬阻断。
- 下载文件不能逃出 browser downloads 目录。
- 通用二进制下载能走 backend storage、attachment routes、SSE/timeline 和 Android rendering。
- `browser_observe` review input 包含 sanitized URL/title；无法证明当前页面归属时阻断。
- `browser_look` review input 包含 sanitized URL/title，无法证明当前页面归属时阻断；成功时只通过 `model_images` 给模型观察截图，不上传 artifact。
- `browser_capture` 仍是 user-facing artifact 工具，不偷偷变成模型视觉输入。
- 浏览器视觉观察不做 OCR、不建立跨 turn 视觉记忆，截图大小受 image byte limit 约束。
- 页面观察不暴露 password / hidden input values。
- 临时 browser screenshots 不无界积累。
- 工具 surface 保持为六个 browser tools。

---

*← [Capabilities 索引](INDEX.md) · [Spec 根索引](../INDEX.md)*
