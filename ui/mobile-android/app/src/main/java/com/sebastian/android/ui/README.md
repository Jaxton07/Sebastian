# ui 层

> 上级：[ui/mobile-android/README.md](../../../../../../../../README.md)

Jetpack Compose UI 层，按功能领域分包，所有 Screen / Page 以 Composable 函数实现。

## 目录结构

```text
ui/
├── chat/
│   ├── ChatScreen.kt       # 主对话 Screen（NavigableListDetailPaneScaffold 三栏）
│   ├── MessageList.kt      # 消息列表（LazyColumn + 滚动跟随逻辑）
│   ├── SessionPanel.kt     # 左栏：Session 列表面板（List Pane）
│   ├── StreamingMessage.kt # 流式消息气泡（逐块渲染）
│   ├── ThinkingCard.kt     # 思考块卡片（可展开/折叠）
│   ├── TodoPanel.kt        # 右栏：Todo 面板（Extra Pane）
│   └── ToolCallCard.kt     # 工具调用块卡片（含状态 badge）
├── common/
│   ├── AnimationTokens.kt  # 全局动画时长常量
│   ├── ApprovalDialog.kt   # 审批对话框（阻断式，出现时其他交互禁用）
│   ├── ErrorBanner.kt      # 错误横幅（可选操作按钮）
│   └── MarkdownView.kt     # AndroidView 封装 Markwon 渲染
├── composer/
│   ├── Composer.kt         # 输入框容器（含 ThinkButton + SendButton）
│   ├── SendButton.kt       # 发送/停止按钮（状态机驱动：IDLE / SENDING / STREAMING / CANCELLING）
│   └── ThinkButton.kt      # 思考档位按钮（AUTO / LOW / HIGH，弹出 EffortPicker）
├── navigation/
│   └── Route.kt            # Type-safe 路由定义（sealed class，kotlinx.serialization）
├── settings/
│   ├── SettingsScreen.kt   # 设置首页（分类卡片列表）
│   ├── ConnectionPage.kt   # 连接与账户页（Server URL / 登录 / 健康检查）
│   ├── ProviderListPage.kt # Provider 列表页
│   └── ProviderFormPage.kt # Provider 新增/编辑页
├── subagents/
│   ├── AgentListScreen.kt  # Sub-Agent 列表页
│   ├── SessionListScreen.kt # 某 Agent 下的 Session 列表页
│   └── SessionDetailScreen.kt # Sub-Agent Session 详情页
└── theme/
    ├── Color.kt            # 品牌色与语义色 token
    └── SebastianTheme.kt   # MaterialTheme 配置（Light / Dark）
```

## 模块说明

### `chat/`

主对话入口，是 App 的默认起始页（`Route.Chat`）。

- **`ChatScreen`**：使用 `NavigableListDetailPaneScaffold` 实现三栏自适应布局：
  - **List Pane**（左栏）：`SessionPanel` — Session 列表 + 导航入口（Settings / SubAgents）
  - **Detail Pane**（中栏）：`MessageList` + `Composer` + 三态 `ErrorBanner`
  - **Extra Pane**（右栏）：`TodoPanel`
  - 手机竖屏单栏，宽屏/折叠屏多栏自动适配
- **`MessageList`**：管理滚动跟随状态（FOLLOWING / DETACHED / NEAR_BOTTOM），由 `flushTick` 驱动每帧滚动更新
- **`StreamingMessage`**：按 `ContentBlock` 类型分发渲染（TextBlock → MarkdownView / ThinkingBlock → ThinkingCard / ToolBlock → ToolCallCard）
- **`ErrorBanner`** 三态：服务器未配置 / 网络断开 / SSE 连接失败（含重试按钮）

### `common/`

跨领域复用组件。

- **`ApprovalDialog`**：高危操作审批弹窗，出现时阻断其他交互，支持 Grant / Deny
- **`MarkdownView`**：`AndroidView` 包裹 `Markwon`，接受预渲染的 `CharSequence`（`renderedMarkdown`）
- **`ErrorBanner`**：可选 `actionLabel` + `onAction` 操作按钮的横幅组件
- **`AnimationTokens`**：统一管理动画时长常量，避免各处硬编码

### `composer/`

消息输入区，状态由 `ChatUiState.composerState` 驱动（`ComposerState` 枚举）。

- **`Composer`**：接收 `ComposerState` / `activeProvider` / `effort`，组合 `ThinkButton` 和 `SendButton`
- **`SendButton`**：IDLE_EMPTY → 灰色禁用；IDLE_READY → 激活发送；STREAMING → 停止按钮；CANCELLING → 加载中
- **`ThinkButton`**：按当前 provider `thinking_capability` 决定是否渲染，点击弹出 `EffortPicker`（AUTO / LOW / HIGH）

### `navigation/`

- **`Route`**：`sealed class`，用 `@Serializable` + `kotlinx.serialization` 实现 type-safe 路由，由 `MainActivity.kt` 的 `NavHost` 注册全部路由

路由表：

| Route | Screen |
|-------|--------|
| `Chat` | `ChatScreen` |
| `SubAgents` | `AgentListScreen` |
| `AgentSessions(agentId)` | `SessionListScreen` |
| `SessionDetail(sessionId)` | `SessionDetailScreen` |
| `Settings` | `SettingsScreen` |
| `SettingsConnection` | `ConnectionPage` |
| `SettingsProviders` | `ProviderListPage` |
| `SettingsProvidersNew` | `ProviderFormPage(null)` |
| `SettingsProvidersEdit(providerId)` | `ProviderFormPage(id)` |

### `settings/`

- **`SettingsScreen`**：设置首页，展示分类卡片（连接与账户 / Provider / 外观 / 高级）
- **`ConnectionPage`**：Server URL 输入、登录/登出、健康检查（连接测试）
- **`ProviderListPage`** / **`ProviderFormPage`**：LLM Provider 列表与新增/编辑，`ProviderFormViewModel` 驱动

### `subagents/`

- **`AgentListScreen`**：展示可用 Sub-Agent，由 `SubAgentViewModel` 驱动
- **`SessionListScreen`**：某 Agent 的 Session 列表，含 FAB 新建 session
- **`SessionDetailScreen`**：Sub-Agent Session 详情（MessageList + Composer），复用 `ChatViewModel`

### `theme/`

- **`SebastianTheme`**：基于 Material3 `MaterialTheme`，封装 Light / Dark 切换
- **`Color.kt`**：品牌色 + 语义色 token，不直接在组件中硬编码颜色

## 修改导航

| 修改场景 | 优先看 |
|---------|--------|
| 改三栏布局（List/Detail/Extra Pane） | `chat/ChatScreen.kt` |
| 改消息渲染（文本/思考/工具调用） | `chat/StreamingMessage.kt`、`chat/ThinkingCard.kt`、`chat/ToolCallCard.kt` |
| 改消息列表滚动行为 | `chat/MessageList.kt` |
| 改 Session 列表面板 | `chat/SessionPanel.kt` |
| 改 Todo 面板 | `chat/TodoPanel.kt` |
| 改输入框样式/行为 | `composer/Composer.kt` |
| 改发送/停止按钮状态 | `composer/SendButton.kt` |
| 改思考档位按钮/选择器 | `composer/ThinkButton.kt` |
| 改审批弹窗 | `common/ApprovalDialog.kt` |
| 改错误横幅 | `common/ErrorBanner.kt` |
| 改 Markdown 渲染视图 | `common/MarkdownView.kt` |
| 新增路由 | `navigation/Route.kt` + `MainActivity.kt` |
| 改设置分类卡片 | `settings/SettingsScreen.kt` |
| 改连接/账户设置 | `settings/ConnectionPage.kt` |
| 改 Provider 管理页 | `settings/ProviderListPage.kt`、`settings/ProviderFormPage.kt` |
| 改品牌色或主题 | `theme/Color.kt`、`theme/SebastianTheme.kt` |

---

> 新增 Screen 或重构页面结构后，请同步更新本 README、路由表与上级 `ui/mobile-android/README.md`。
