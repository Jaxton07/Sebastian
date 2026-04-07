# composer/

Composer 是主对话输入区组件，负责文本输入、思考开关、发送/停止控制。

由 `KeyboardStickyView`（父层）包裹实现键盘跟随，自身无需感知键盘高度。

## 文件职责

| 文件 | 职责 |
|---|---|
| `index.tsx` | 主组件。状态机管理，组合子组件，普通 View 布局 |
| `InputTextArea.tsx` | 多行 TextInput，最多 5 行，超出内部滚动 |
| `ActionsRow.tsx` | 底部按钮容器，左思考右发送布局 |
| `ThinkButton.tsx` | 胶囊式思考开关（UI 占位，未接后端） |
| `SendButton.tsx` | 圆形按钮，根据 ComposerState 渲染 4 种视觉 |
| `types.ts` | `ComposerState` 5 状态枚举 |
| `constants.ts` | 行高、最大行数等布局常量（含 `COMPOSER_DEFAULT_HEIGHT`） |

## 状态机

```
idle_empty ──has text──→ idle_ready
idle_ready ──send──────→ sending ──activeTurn──→ streaming ──stop──→ cancelling
streaming  ──turn done→ idle_empty
cancelling ──turn done→ idle_empty
cancelling ──5s timeout→ idle_empty + toast
```

## Props (Composer)

| Prop | 类型 | 说明 |
|---|---|---|
| `sessionId` | `string \| null` | null = draft session |
| `isWorking` | `boolean` | 来自 conversationStore.activeTurn |
| `onSend` | `(text, opts) => Promise<void>` | `opts.thinking` 预留字段 |
| `onStop` | `() => Promise<void>` | 调用 cancelTurn API |

> **已移除**：~~`bottomInset`~~、~~`onHeightChange`~~。键盘适配完全由外层 `KeyboardStickyView` 处理，Composer 无需上报高度。

## 键盘布局方案（react-native-keyboard-controller）

Composer 本身是普通 `View`（`marginHorizontal: 12, marginBottom: 12`），不做任何键盘感知。
键盘行为由父层控制：

- **`KeyboardStickyView`**（`app/index.tsx`、`app/subagents/session/[id].tsx`）：包裹 Composer，原生帧同步跟随键盘上移/下移，无 Yoga 重排抖动。
- **`stickyOffset = { opened: insets.bottom }`**：SafeAreaView 提供的底部安全区已包含在 `KeyboardStickyView` 基准位置中，`opened` 偏移补偿避免双重叠加。
- 消息列表用 `KeyboardChatScrollView`（通过 `renderScrollComponent` 注入 FlatList），自动通过 contentInset 调整滚动区域，无需手动计算 paddingBottom。

## 思考开关

状态存于 `src/store/composer.ts` 的 `useComposerStore`，按 `sessionId` 隔离。
Draft session 用 `__draft__` key，`persistSession` 后调 `migrateDraftToSession(newId)` 迁移。
