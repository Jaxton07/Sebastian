# composer 模块

> 上级：[ui/README.md](../README.md)

消息输入区，由 `ChatUiState.composerState`（`ComposerState` 枚举）驱动，封装输入框、发送/停止按钮与思考档位选择器。

## 目录结构

```text
composer/
├── Composer.kt         # 输入框容器（组合 ThinkButton + SendButton，GlassSurface 悬浮）
├── EffortPickerCard.kt # 思考档位选择卡片（GlassSurface 效果，由 ChatScreen 根 Box 渲染）
├── SendButton.kt       # 发送/停止按钮（状态机驱动）
└── ThinkButton.kt      # 思考档位按钮（点击展开 EffortPickerCard）
```

## 模块说明

### `Composer`

接收 `ComposerState` / `activeProvider` / `effort`，通过 `GlassSurface` 实现液态玻璃悬浮效果，内部组合 `ThinkButton` 和 `SendButton`。

### `SendButton`

状态机驱动，四个状态对应不同视觉与行为：

| 状态 | 触发条件 | 视觉 |
|------|---------|------|
| `IDLE_EMPTY` | 输入框为空 | 灰色禁用 |
| `IDLE_READY` | 有输入内容 | 激活发送图标 |
| `STREAMING` | AI 正在响应 | 停止按钮 |
| `CANCELLING` | 已发送停止请求 | 加载中 |

### `ThinkButton`

按当前 Provider `thinking_capability` 决定是否渲染。点击展开 `EffortPickerCard`，可选档位视 capability 而定（`OFF` / `LOW` / `MEDIUM` / `HIGH`，ADAPTIVE 模式额外有 `MAX`）。

### `EffortPickerCard`

思考档位选择卡片，使用 `GlassSurface` 实现背景模糊效果。

> **重要**：必须由 `ChatScreen` 直接在根 `Box` 中渲染，**不能**放进 `Popup` / `Dialog`——backdrop 采样依赖与 `GlassState.contentModifier` 同处一棵 composable 树。

## 修改导航

| 修改场景 | 优先看 |
|---------|--------|
| 改输入框整体布局/悬浮样式 | `Composer.kt` |
| 改发送/停止按钮状态逻辑 | `SendButton.kt` |
| 改思考档位按钮触发逻辑 | `ThinkButton.kt` |
| 改思考档位选择卡片样式/选项 | `EffortPickerCard.kt` |
| 改 `ComposerState` 枚举定义 | `viewmodel/ChatViewModel.kt` |

---

> 新增输入区控件后，请同步更新本 README 与上级 [ui/README.md](../README.md)。
