# Android 执行步骤外层折叠设计

## 背景

一次较长的 assistant 回复可能会在真正面向用户的答案前产生很多连续的 `ThinkingBlock` 和 `ToolBlock`。Android App 当前在 `StreamingMessage.kt` 中把这些 block 平铺渲染，长任务会显得很吵，也容易让用户误以为界面卡住，哪怕后端其实仍在执行。

目标是压缩执行过程的视觉占用，但不隐藏“还在工作”的反馈。连续的 thinking/tool blocks 应收进一个外层执行组；折叠时显示紧凑的执行时间线，展开后仍显示现有的 thinking 和 tool 明细卡片。

## 范围

- 仅影响 Android 原生 App：`ui/mobile-android`。
- 仅影响 assistant 消息。
- 连续的 `ThinkingBlock` / `ToolBlock` 会被聚合成一组。
- 执行组从第一个 thinking/tool block 开始，遇到下一个非 thinking/tool block 前结束。
- `TextBlock`、`SummaryBlock`、`ImageBlock`、`FileBlock` 的渲染保持不变。
- 不改 SSE 协议，不改后端。

## 交互设计

### 折叠态

折叠态是一个无边框、单行的执行时间线，嵌在 assistant 消息流里。

- 左侧显示展开箭头。
- 主区域显示可横向滑动的竖胶囊步骤条。
- 每个竖胶囊代表一个 thinking/tool block，按真实执行顺序从左到右追加。
- 成功或已完成的步骤显示绿色。
- 当前正在执行的步骤显示绿色，并带轻微缩放/闪烁动画。
- 失败步骤显示红色。
- 不显示未来占位胶囊。
- 主行不显示“执行步骤”等标题文字。
- 不显示颜色图例。
- 如需显示总数，数字必须放在滚动区域外，且不能遮住最后一个胶囊。

步骤过多时，时间线保持单行并横向滑动。新增步骤或当前步骤状态变化时，时间线自动滚到最右侧。最后一个胶囊，尤其是正在执行的胶囊，必须完整可见。视觉渐隐最多只允许放在左侧，用于提示前面还有历史步骤；右侧不能用渐隐遮挡最新步骤。

### 展开态

点击执行组后在原位置展开，显示这组内原始的 block 序列。

- `ThinkingCard` 保留现有展开/折叠行为。
- `ToolCallCard` 保留现有状态、摘要、输出展开行为。
- 外层执行组的展开不移除单个 block 自己的展开控制。
- 用户可从同一 header 行再次收起外层执行组。

### 完成态

当组内所有 block 结束后，运行中的闪烁动画停止。

- 完成的 thinking/tool 步骤保持绿色。
- 失败的 tool 步骤保持红色。
- 除非用户已手动展开，否则完成后的执行组默认保持折叠。
- 完成后的执行组作为紧凑的执行历史存在。

## 架构设计

改动应集中在 Android UI / 消息渲染层。

### 数据模型

第一版不新增持久化的 `ContentBlock` 类型。执行组由 `StreamingMessage.kt` 基于现有 `List<ContentBlock>` 临时分组得到。

在 chat UI 层附近新增一个仅用于渲染的轻量模型：

- `MessageRenderItem.Block(block: ContentBlock)`
- `MessageRenderItem.ExecutionGroup(id: String, blocks: List<ContentBlock>)`

执行组 id 可由组内首尾 block id 派生，保证 Compose key 稳定，同时不影响网络和存储模型。

### 组件

在 `ui/chat/` 下新增 `ExecutionGroupCard` composable。

职责：

- 渲染无边框折叠行。
- 渲染横向滑动的竖胶囊时间线。
- 新步骤到达时自动滚到最新步骤。
- 管理外层展开/折叠。
- 展开后委托现有 `ThinkingCard` 和 `ToolCallCard` 渲染明细。

`StreamingMessage.kt` 在渲染 assistant 消息前，把 blocks 转换为 render items：普通 block 走现有渲染路径，连续 thinking/tool blocks 走 `ExecutionGroupCard`。

### 状态

第一版中，外层执行组的展开/折叠状态保持 UI-local，使用 `rememberSaveable(groupId)`。这与“不新增持久化 `ContentBlock` 类型”的决策一致，也避免为了纯展示分组扩大 `ChatViewModel` 状态面。

只有当后续产品要求“外层执行组展开状态必须在切换 session 或完整历史水合后保留”时，再考虑把该状态移动到 `ChatViewModel`。

单个 block 的现有状态保持不变：

- `toggleThinkingBlock`
- `toggleToolBlock`
- `toggleSummaryBlock`

## 数据流

1. SSE 事件继续更新 `ChatViewModel` 中现有的 `ContentBlock`。
2. `MessageBubble` 收到更新后的 assistant message。
3. `StreamingMessage.kt` 把连续 thinking/tool blocks 分组成 `ExecutionGroup` render item。
4. `ExecutionGroupCard` 根据每个 block 派生竖胶囊状态：
   - `ThinkingBlock(done=false)` -> 绿色运行中闪烁
   - `ThinkingBlock(done=true)` -> 绿色
   - 最新的非终态 `ToolBlock(PENDING/RUNNING)` -> 绿色运行中闪烁
   - `ToolBlock(DONE)` -> 绿色
   - `ToolBlock(FAILED)` -> 红色
5. 新的步骤进入执行组时，横向时间线滚动到末尾。
6. 展开态用现有组件渲染原始 thinking/tool 明细。

## 边界情况

- 空执行组：不渲染。
- 单个 thinking/tool block：仍渲染为一个一格胶囊的执行组，保持视觉一致。
- 多个失败 tool call：每个失败步骤在原顺序位置显示为红色。
- 很长的执行组：保持单行、横向滑动，并确保最新胶囊完整可见。
- 混合内容：遇到文本、图片、文件、summary 时结束当前执行组。
- 历史消息水合：同样基于现有 blocks 临时分组，行为与实时 SSE 消息一致。

## 测试

新增聚焦于纯分组逻辑的 Android 单元测试：

- 连续 thinking/tool blocks 会变成一个执行组。
- `TextBlock` 会切分执行组。
- 附件和 summary 会切分执行组。
- 单个 thinking/tool block 也会变成执行组。
- 非执行 block 的原始顺序保持不变。

在可行范围内补充 Compose/UI 检查：

- 多个执行 block 折叠后只占一行执行组。
- 失败 tool 步骤能与成功步骤区分。
- 展开执行组后能看到原有 thinking/tool 明细。

手动验证：

- 运行一个包含多个工具调用的长 assistant 任务。
- 确认折叠态高度稳定。
- 确认最新运行中的胶囊完整可见。
- 确认展开后显示原始 thinking/tool 明细。
