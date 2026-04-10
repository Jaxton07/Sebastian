# SwipePager 平铺滑动侧边栏设计

> 日期：2026-04-10
> 状态：已批准，待实施

## 背景

当前 App 的左右侧边栏采用 overlay 模式（`Sidebar.tsx`），侧边栏从屏幕边缘滑入覆盖在对话页面上方，带半透明遮罩。交互上只有阈值触发的开/关，没有跟手拖拽动画。

目标是改为类似 DeepSeek App 的平铺滑动风格：三个面板（左侧边栏 / 对话 / 右侧边栏）水平排列，手势拖拽时整体跟手移动，松手后弹性 snap 到目标面板，视觉上像在三个并列页面间滑动。

## 需求

- 主对话页（`app/index.tsx`）：左（AppSidebar）+ 右（TodoSidebar）双侧边栏平铺滑动
- Sub-Agent Session 详情页（`app/subagents/session/[id].tsx`）：仅右（TodoSidebar）单侧边栏
- 侧边栏占屏幕宽度约 80%，展开时对话页露出约 20%
- Header 随对话面板一起滑走，侧边栏有各自独立的顶部区域
- 跟手拖拽 + 惯性 snap，松手后根据速度和位置决定目标面板
- 动画全程 UI 线程运行，支持 90/120fps 高刷屏

## 技术方案

### 选型：Reanimated + Gesture Handler

使用项目已有的 `react-native-reanimated` (4.1.x) + `react-native-gesture-handler` (2.28.x)，零新增依赖。

核心原理：`Gesture.Pan()` 驱动 `useSharedValue(translateX)`，通过 `useAnimatedStyle` 实时更新面板组的水平位移，松手后 `withSpring` snap 到目标位置。所有动画代码作为 worklet 运行在 UI 线程。

### SwipePager 组件

新建 `src/components/common/SwipePager.tsx`，约 150-200 行。

#### 接口

```tsx
interface SwipePagerProps {
  left?: ReactNode;       // 左侧边栏内容（可选）
  right?: ReactNode;      // 右侧边栏内容（可选）
  children: ReactNode;    // 中间主内容（含 Header）
  sidebarWidth?: number;  // 侧边栏宽度比例，默认 0.8
  onPanelChange?: (panel: 'left' | 'center' | 'right') => void;
}

interface SwipePagerRef {
  goToCenter: () => void;
  goToLeft: () => void;
  goToRight: () => void;
}
```

#### 面板布局

三个面板用 `Animated.View` 水平排列在一个容器中：

- 左面板宽度：`screenWidth * sidebarWidth`（默认 80%）
- 中间面板宽度：`screenWidth`（100%）
- 右面板宽度：`screenWidth * sidebarWidth`（默认 80%）

视口（屏幕）通过 `translateX` 在这条水平带上滑动。

#### Snap 点计算

三个面板总宽 = `leftW + screenW + rightW`，视口宽 = `screenW`。translateX 控制面板组相对视口的偏移：

```
leftSnap   = 0                          // 视口对齐左面板左边缘，左面板全部可见，对话页露出 screenW - leftW（≈20%）
centerSnap = -leftW                     // 视口对齐中间面板左边缘，对话页完整可见
rightSnap  = -(leftW + rightW)          // 右面板右边缘对齐屏幕右边缘，对话页露出 screenW - rightW（≈20%）
```

其中 `leftW = rightW = screenWidth * sidebarWidth`（默认 80%）。

不传 `left` 时，面板组只有中间 + 右，snap 点为 `[0, -rightSidebarWidthPx]`，向右拖拽 clamp 在 0。

#### 手势逻辑（worklet）

1. **onStart**：记录当前 `translateX` 为起点
2. **onUpdate**：`translateX.value = clamp(startX + translationX, minSnap, maxSnap + rubberBand)`
3. **onEnd**：
   - 快速轻扫（`|velocityX| > 500`）：直接切到速度方向的下一面板
   - 否则：snap 到距离最近的 snap 点
   - 使用 `withSpring({ damping: 20, stiffness: 200 })` 过渡（参数可调）
4. **边界阻尼**：超出边界时 `translationX * 0.3`，松手弹回

#### 命令式 API

通过 `forwardRef` + `useImperativeHandle` 暴露 `goToCenter/goToLeft/goToRight`，内部调用 `withSpring` 将 `translateX` 设到对应 snap 点。

用于：
- Header 汉堡按钮点击 → `goToLeft()`
- 侧边栏内的关闭/选择操作 → `goToCenter()`

### 手势冲突处理

| 场景 | 策略 |
|------|------|
| FlatList 纵向滚动 | `Gesture.Pan()` 设置 `activeOffsetX([-15, 15])` + `failOffsetY([-10, 10])`，纵向移动优先让给 FlatList |
| KeyboardGestureArea 滑动收键盘 | 键盘手势是纵向的，与水平 Pan 天然不冲突 |
| Composer 输入框光标拖拽 | SwipePager 手势 hitSlop 排除 Composer 区域，或 `simultaneousHandlers` 让输入框内手势优先 |
| 侧边栏内部 ScrollView | 纵向滚动与水平 Pan 靠 `activeOffsetX` 区分，不冲突 |

### 页面集成

#### 主对话页 `app/index.tsx`

```tsx
<SwipePager
  ref={pagerRef}
  left={<AppSidebar ... onClose={() => pagerRef.current?.goToCenter()} />}
  right={<TodoSidebar ... onClose={() => pagerRef.current?.goToCenter()} />}
  onPanelChange={(panel) => { /* 可选副作用 */ }}
>
  <Header />
  <KeyboardGestureArea ...>
    <ConversationView ... />
    <KeyboardStickyView ...>
      <Composer ... />
    </KeyboardStickyView>
  </KeyboardGestureArea>
</SwipePager>
```

变化：
- 移除 `sidebarOpen` / `todoSidebarOpen` 状态
- 移除 `<Sidebar>` 和 `<ContentPanGestureArea>` 的使用
- Header 汉堡按钮 onPress 改为 `pagerRef.current?.goToLeft()`

#### Sub-Agent Session 详情页 `app/subagents/session/[id].tsx`

```tsx
<SwipePager
  ref={pagerRef}
  right={<TodoSidebar ... onClose={() => pagerRef.current?.goToCenter()} />}
>
  <Header with BackButton />
  <KeyboardGestureArea ...>
    ...
  </KeyboardGestureArea>
</SwipePager>
```

不传 `left`，SwipePager 只生成双面板，向右拖拽 clamp。

## 文件变更清单

### 新增

- `src/components/common/SwipePager.tsx` — 核心平铺滑动组件

### 修改

- `app/index.tsx` — 用 SwipePager 包裹，移除 Sidebar/ContentPanGestureArea/sidebar 状态
- `app/subagents/session/[id].tsx` — 同上，只传 right
- `src/components/chat/AppSidebar.tsx` — `onClose` 接口不变，调用方改为 `goToCenter()`
- `src/components/chat/TodoSidebar.tsx` — 同上

### 删除

- `src/components/common/Sidebar.tsx` — 被 SwipePager 完全替代
- `src/components/common/ContentPanGestureArea.tsx` — 被 SwipePager 完全替代

### README 更新

- `ui/mobile/README.md` — 修改导航表中 Sidebar/ContentPanGestureArea 条目，新增 SwipePager
- `src/components/common/README.md`（若存在）— 同步更新

### 不改动

- AppSidebar / TodoSidebar 的内容和样式
- 键盘适配方案（KeyboardProvider / KeyboardStickyView / KeyboardChatScrollView）
- 路由结构
