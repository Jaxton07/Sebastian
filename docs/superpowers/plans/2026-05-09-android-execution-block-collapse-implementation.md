# Android Execution Block Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Android 聊天消息流中，把连续的 thinking/tool blocks 收进一个可展开的外层执行组，折叠态用单行横向滑动竖胶囊步骤条展示执行进度。

**Architecture:** 不改 SSE、后端、持久化模型，也不新增 `ContentBlock` 类型。`StreamingMessage.kt` 渲染前先把现有 `List<ContentBlock>` 转换为 UI-only render items；连续 `ThinkingBlock` / `ToolBlock` 变成 `ExecutionGroup`，由新的 `ExecutionGroupCard` 渲染。分组逻辑是纯 Kotlin 函数，先用单元测试锁定，再接 Compose UI。

**Tech Stack:** Kotlin, Jetpack Compose, Material3, Android unit tests via Gradle/JUnit4.

---

## Current Worktree Note

当前分支是 `codex/skill-package-manager-spec`。用户明确要求继续在这个分支上工作，不要另开新分支。

开始实现前保留已有未提交文件：

- `docs/superpowers/specs/2026-05-09-android-execution-block-collapse-design.md`
- `docs/superpowers/plans/2026-05-09-android-execution-block-collapse-implementation.md`

不要用 `git add .`，提交时逐文件添加。

## File Structure

- Create `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionRenderItems.kt`
  - 定义 `MessageRenderItem`、`ExecutionStepState`。
  - 提供 `buildMessageRenderItems(blocks)` 纯函数。
  - 提供 `executionStepState(block)` 纯函数。
- Create `ui/mobile-android/app/src/test/java/com/sebastian/android/ui/chat/ExecutionRenderItemsTest.kt`
  - 覆盖连续分组、非执行 block 切分、单 block 分组、顺序保持、状态映射。
- Create `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionGroupCard.kt`
  - 渲染外层折叠组。
  - 折叠态显示单行横向滑动竖胶囊步骤条。
  - 展开态复用 `ThinkingCard` 和 `ToolCallCard`。
- Modify `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/StreamingMessage.kt`
  - 将 assistant blocks 的 `forEach` 渲染改为 render items 渲染。
  - 保留普通 block 原有渲染路径。
- Modify `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/README.md`
  - 更新目录结构与 `StreamingMessage` / 新组件说明。
- Modify `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/README.md`
  - 在修改导航中补充执行步骤外层折叠入口，或更新消息渲染说明。
- Optional Modify `ui/mobile-android/README.md`
  - 如果修改导航需要更精确，补充 `ExecutionGroupCard.kt`。

`StreamingMessage.kt` 当前约 200 行，没有超过仓库 500 行建议；本计划仍新增独立文件承载分组和新 UI，避免继续膨胀消息渲染分发文件。

## Task 1: Add Pure Render Grouping Model

**Files:**
- Create: `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionRenderItems.kt`
- Test: `ui/mobile-android/app/src/test/java/com/sebastian/android/ui/chat/ExecutionRenderItemsTest.kt`

- [ ] **Step 1: Write failing grouping tests**

Create `ExecutionRenderItemsTest.kt`:

```kotlin
package com.sebastian.android.ui.chat

import com.sebastian.android.data.model.ContentBlock
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExecutionRenderItemsTest {

    @Test
    fun `consecutive thinking and tool blocks become one execution group`() {
        val blocks = listOf(
            ContentBlock.ThinkingBlock(blockId = "think-1", text = "plan", done = true),
            ContentBlock.ToolBlock(
                blockId = "tool-1",
                toolId = "call-1",
                name = "read_file",
                displayName = "Read file",
                inputs = "{}",
                status = ToolStatus.DONE,
            ),
        )

        val items = buildMessageRenderItems(blocks)

        assertEquals(1, items.size)
        val group = items.single() as MessageRenderItem.ExecutionGroup
        assertEquals("exec-think-1-tool-1", group.id)
        assertEquals(blocks, group.blocks)
    }

    @Test
    fun `text block splits execution groups and preserves order`() {
        val first = ContentBlock.ThinkingBlock(blockId = "think-1", text = "plan", done = true)
        val text = ContentBlock.TextBlock(blockId = "text-1", text = "answer", done = true)
        val second = ContentBlock.ToolBlock(
            blockId = "tool-1",
            toolId = "call-1",
            name = "search",
            displayName = "Search",
            inputs = "{}",
            status = ToolStatus.RUNNING,
        )

        val items = buildMessageRenderItems(listOf(first, text, second))

        assertEquals(3, items.size)
        assertTrue(items[0] is MessageRenderItem.ExecutionGroup)
        assertEquals(text, (items[1] as MessageRenderItem.Block).block)
        assertTrue(items[2] is MessageRenderItem.ExecutionGroup)
    }

    @Test
    fun `summary image and file blocks split execution groups`() {
        val think = ContentBlock.ThinkingBlock(blockId = "think-1", text = "plan")
        val summary = ContentBlock.SummaryBlock(blockId = "summary-1", text = "compressed")
        val image = ContentBlock.ImageBlock(
            blockId = "image-1",
            attachmentId = "att-image",
            filename = "shot.png",
            mimeType = "image/png",
            sizeBytes = 10L,
            downloadUrl = "/download/image",
        )
        val file = ContentBlock.FileBlock(
            blockId = "file-1",
            attachmentId = "att-file",
            filename = "notes.txt",
            mimeType = "text/plain",
            sizeBytes = 20L,
            downloadUrl = "/download/file",
        )
        val tool = ContentBlock.ToolBlock(
            blockId = "tool-1",
            toolId = "call-1",
            name = "read",
            inputs = "{}",
            status = ToolStatus.DONE,
        )

        val items = buildMessageRenderItems(listOf(think, summary, image, file, tool))

        assertEquals(5, items.size)
        assertTrue(items[0] is MessageRenderItem.ExecutionGroup)
        assertEquals(summary, (items[1] as MessageRenderItem.Block).block)
        assertEquals(image, (items[2] as MessageRenderItem.Block).block)
        assertEquals(file, (items[3] as MessageRenderItem.Block).block)
        assertTrue(items[4] is MessageRenderItem.ExecutionGroup)
    }

    @Test
    fun `single execution block still becomes execution group`() {
        val block = ContentBlock.ToolBlock(
            blockId = "tool-1",
            toolId = "call-1",
            name = "read",
            inputs = "{}",
            status = ToolStatus.DONE,
        )

        val items = buildMessageRenderItems(listOf(block))

        assertEquals(1, items.size)
        assertEquals(listOf(block), (items.single() as MessageRenderItem.ExecutionGroup).blocks)
    }
}
```

- [ ] **Step 2: Run tests to verify failure**

Run from `ui/mobile-android`:

```bash
./gradlew :app:testDebugUnitTest --tests "com.sebastian.android.ui.chat.ExecutionRenderItemsTest"
```

Expected: FAIL because `ExecutionRenderItems.kt`, `MessageRenderItem`, and `buildMessageRenderItems` do not exist.

- [ ] **Step 3: Implement the minimal render grouping model**

Create `ExecutionRenderItems.kt`:

```kotlin
package com.sebastian.android.ui.chat

import com.sebastian.android.data.model.ContentBlock
import com.sebastian.android.data.model.ToolStatus

sealed interface MessageRenderItem {
    data class Block(val block: ContentBlock) : MessageRenderItem
    data class ExecutionGroup(
        val id: String,
        val blocks: List<ContentBlock>,
    ) : MessageRenderItem
}

enum class ExecutionStepState {
    DONE,
    RUNNING,
    FAILED,
}

fun buildMessageRenderItems(blocks: List<ContentBlock>): List<MessageRenderItem> {
    val items = mutableListOf<MessageRenderItem>()
    val pendingExecutionBlocks = mutableListOf<ContentBlock>()

    fun flushExecutionGroup() {
        if (pendingExecutionBlocks.isEmpty()) return
        val firstId = pendingExecutionBlocks.first().blockId
        val lastId = pendingExecutionBlocks.last().blockId
        items += MessageRenderItem.ExecutionGroup(
            id = "exec-$firstId-$lastId",
            blocks = pendingExecutionBlocks.toList(),
        )
        pendingExecutionBlocks.clear()
    }

    for (block in blocks) {
        if (block.isExecutionBlock()) {
            pendingExecutionBlocks += block
        } else {
            flushExecutionGroup()
            items += MessageRenderItem.Block(block)
        }
    }
    flushExecutionGroup()

    return items
}

fun ContentBlock.isExecutionBlock(): Boolean =
    this is ContentBlock.ThinkingBlock || this is ContentBlock.ToolBlock
```

- [ ] **Step 4: Run grouping tests to verify pass**

Run:

```bash
./gradlew :app:testDebugUnitTest --tests "com.sebastian.android.ui.chat.ExecutionRenderItemsTest"
```

Expected: PASS.

- [ ] **Step 5: Commit grouping model**

```bash
git add ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionRenderItems.kt ui/mobile-android/app/src/test/java/com/sebastian/android/ui/chat/ExecutionRenderItemsTest.kt
git commit -m "feat(android): 增加执行步骤渲染分组模型" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

## Task 2: Add Step State Tests

**Files:**
- Modify: `ui/mobile-android/app/src/test/java/com/sebastian/android/ui/chat/ExecutionRenderItemsTest.kt`
- Modify: `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionRenderItems.kt`

- [ ] **Step 1: Add failing tests for capsule state mapping**

Append to `ExecutionRenderItemsTest.kt`:

```kotlin
@Test
fun `executionStepState maps thinking states`() {
    assertEquals(
        ExecutionStepState.RUNNING,
        executionStepState(ContentBlock.ThinkingBlock(blockId = "think-running", text = "")),
    )
    assertEquals(
        ExecutionStepState.DONE,
        executionStepState(ContentBlock.ThinkingBlock(blockId = "think-done", text = "", done = true)),
    )
}

@Test
fun `executionStepState maps tool states`() {
    fun tool(status: ToolStatus) = ContentBlock.ToolBlock(
        blockId = "tool-$status",
        toolId = "call-$status",
        name = "tool",
        inputs = "{}",
        status = status,
    )

    assertEquals(ExecutionStepState.RUNNING, executionStepState(tool(ToolStatus.PENDING)))
    assertEquals(ExecutionStepState.RUNNING, executionStepState(tool(ToolStatus.RUNNING)))
    assertEquals(ExecutionStepState.DONE, executionStepState(tool(ToolStatus.DONE)))
    assertEquals(ExecutionStepState.FAILED, executionStepState(tool(ToolStatus.FAILED)))
}
```

- [ ] **Step 2: Run tests**

Run:

```bash
./gradlew :app:testDebugUnitTest --tests "com.sebastian.android.ui.chat.ExecutionRenderItemsTest"
```

Expected: FAIL because `executionStepState` does not exist yet.

- [ ] **Step 3: Implement missing state mapping if needed**

Add `ToolStatus` import and the state mapper to `ExecutionRenderItems.kt`:

```kotlin
import com.sebastian.android.data.model.ToolStatus

fun executionStepState(block: ContentBlock): ExecutionStepState = when (block) {
    is ContentBlock.ThinkingBlock ->
        if (block.done) ExecutionStepState.DONE else ExecutionStepState.RUNNING
    is ContentBlock.ToolBlock -> when (block.status) {
        ToolStatus.DONE -> ExecutionStepState.DONE
        ToolStatus.FAILED -> ExecutionStepState.FAILED
        ToolStatus.PENDING, ToolStatus.RUNNING -> ExecutionStepState.RUNNING
    }
    else -> error("Non-execution block has no execution step state: ${block::class.simpleName}")
}
```

- [ ] **Step 4: Run tests again**

Run:

```bash
./gradlew :app:testDebugUnitTest --tests "com.sebastian.android.ui.chat.ExecutionRenderItemsTest"
```

Expected: PASS.

- [ ] **Step 5: Commit state mapping tests if they were separate**

```bash
git add ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionRenderItems.kt ui/mobile-android/app/src/test/java/com/sebastian/android/ui/chat/ExecutionRenderItemsTest.kt
git commit -m "test(android): 覆盖执行步骤状态映射" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

If Task 1 already committed these tests and implementation together, skip this commit.

## Task 3: Add ExecutionGroupCard UI Component

**Files:**
- Create: `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionGroupCard.kt`

- [ ] **Step 1: Create the component skeleton**

Create `ExecutionGroupCard.kt` with:

```kotlin
package com.sebastian.android.ui.chat

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.sebastian.android.data.model.ContentBlock

@Composable
fun ExecutionGroupCard(
    group: MessageRenderItem.ExecutionGroup,
    onToggleThinking: (String) -> Unit,
    onToggleTool: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by rememberSaveable(group.id) { mutableStateOf(false) }

    Column(modifier = modifier.fillMaxWidth()) {
        ExecutionGroupHeader(
            blocks = group.blocks,
            expanded = expanded,
            onToggle = { expanded = !expanded },
        )

        AnimatedVisibility(
            visible = expanded,
            enter = fadeIn(animationSpec = tween(durationMillis = 200)) +
                expandVertically(animationSpec = tween(durationMillis = 260)),
            exit = fadeOut(animationSpec = tween(durationMillis = 160)) +
                shrinkVertically(animationSpec = tween(durationMillis = 220)),
        ) {
            ExecutionGroupDetails(
                blocks = group.blocks,
                onToggleThinking = onToggleThinking,
                onToggleTool = onToggleTool,
            )
        }
    }
}
```

Fix imports after adding the helper composables below. Keep the component borderless and avoid adding a right-edge fade over the newest capsule.

- [ ] **Step 2: Add the borderless collapsed header**

In the same file, add:

```kotlin
@Composable
private fun ExecutionGroupHeader(
    blocks: List<ContentBlock>,
    expanded: Boolean,
    onToggle: () -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val mutedColor = MaterialTheme.colorScheme.onSurfaceVariant

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                onClick = onToggle,
            )
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = if (expanded) {
                Icons.Default.KeyboardArrowDown
            } else {
                Icons.AutoMirrored.Filled.KeyboardArrowRight
            },
            contentDescription = if (expanded) "折叠执行步骤" else "展开执行步骤",
            tint = mutedColor.copy(alpha = 0.72f),
            modifier = Modifier.size(20.dp),
        )
        Spacer(Modifier.width(8.dp))
        ExecutionCapsuleTimeline(
            blocks = blocks,
            modifier = Modifier.weight(1f),
        )
    }
}
```

- [ ] **Step 3: Add the horizontal capsule timeline**

Add:

```kotlin
@Composable
private fun ExecutionCapsuleTimeline(
    blocks: List<ContentBlock>,
    modifier: Modifier = Modifier,
) {
    val scrollState = rememberScrollState()
    val signature = remember(blocks) {
        blocks.joinToString("|") { block ->
            "${block.blockId}:${executionStepState(block)}"
        }
    }

    LaunchedEffect(signature, scrollState.maxValue) {
        withFrameNanos { }
        scrollState.scrollTo(scrollState.maxValue)
    }

    Row(
        modifier = modifier
            .height(36.dp)
            .horizontalScroll(scrollState)
            .padding(start = 2.dp, end = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        blocks.forEach { block ->
            ExecutionCapsule(state = executionStepState(block))
            Spacer(Modifier.width(6.dp))
        }
    }
}
```

Implementation note: the right edge must not have a fade overlay. This is what guarantees the latest capsule can be fully visible. If a left-side fade is added later, it must not cover the right edge.

- [ ] **Step 4: Add the capsule primitive**

Add:

```kotlin
@Composable
private fun ExecutionCapsule(state: ExecutionStepState) {
    val infiniteTransition = rememberInfiniteTransition(label = "execution-capsule")
    val runningScale by infiniteTransition.animateFloat(
        initialValue = 0.78f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 920),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "running-scale",
    )

    val color = when (state) {
        ExecutionStepState.DONE -> Color(0xFF22C55E)
        ExecutionStepState.RUNNING -> Color(0xFF22C55E)
        ExecutionStepState.FAILED -> Color(0xFFEF4444)
    }
    val scaleY = if (state == ExecutionStepState.RUNNING) runningScale else 1f

    Box(
        modifier = Modifier
            .width(8.dp)
            .height(28.dp)
            .scale(scaleX = 1f, scaleY = scaleY)
            .background(color = color, shape = RoundedCornerShape(percent = 50)),
    )
}
```

- [ ] **Step 5: Add expanded details**

Add:

```kotlin
@Composable
private fun ExecutionGroupDetails(
    blocks: List<ContentBlock>,
    onToggleThinking: (String) -> Unit,
    onToggleTool: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 28.dp, top = 4.dp),
    ) {
        blocks.forEach { block ->
            when (block) {
                is ContentBlock.ThinkingBlock -> ThinkingCard(
                    block = block,
                    onToggle = { onToggleThinking(block.blockId) },
                    modifier = Modifier.fillMaxWidth(),
                )
                is ContentBlock.ToolBlock -> ToolCallCard(
                    block = block,
                    onToggle = { onToggleTool(block.blockId) },
                    modifier = Modifier.fillMaxWidth(),
                )
                else -> {}
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}
```

- [ ] **Step 6: Compile to catch Compose/import issues**

Run from `ui/mobile-android`:

```bash
./gradlew :app:compileDebugKotlin
```

Expected: PASS. If imports fail, use IDE organize imports or remove unused imports. Keep the component borderless.

- [ ] **Step 7: Commit the UI component**

```bash
git add ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/ExecutionGroupCard.kt
git commit -m "feat(android): 新增执行步骤折叠组件" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

## Task 4: Integrate Execution Groups Into StreamingMessage

**Files:**
- Modify: `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/StreamingMessage.kt`

- [ ] **Step 1: Replace flat block iteration with render item iteration**

In `AssistantMessageBlocks`, replace:

```kotlin
blocks.forEach { block ->
    key(block.blockId) {
        ...
    }
}
```

with:

```kotlin
val renderItems = remember(blocks) { buildMessageRenderItems(blocks) }

renderItems.forEach { item ->
    when (item) {
        is MessageRenderItem.Block -> {
            val block = item.block
            key(block.blockId) {
                val alpha = alphaMap[block.blockId]?.value ?: 1f
                RenderStandaloneBlock(
                    msgId = msgId,
                    block = block,
                    alpha = alpha,
                    onToggleSummary = onToggleSummary,
                )
                Spacer(Modifier.height(8.dp))
            }
        }
        is MessageRenderItem.ExecutionGroup -> {
            key(item.id) {
                ExecutionGroupCard(
                    group = item,
                    onToggleThinking = { blockId -> onToggleThinking(msgId, blockId) },
                    onToggleTool = { blockId -> onToggleTool(msgId, blockId) },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}
```

- [ ] **Step 2: Extract standalone block rendering helper**

Still in `StreamingMessage.kt`, below `AssistantMessageBlocks`, add:

```kotlin
@Composable
private fun RenderStandaloneBlock(
    msgId: String,
    block: ContentBlock,
    alpha: Float,
    onToggleSummary: (String, String) -> Unit,
) {
    when (block) {
        is ContentBlock.TextBlock -> MarkdownView(
            text = block.text,
            modifier = Modifier
                .fillMaxWidth()
                .alpha(alpha),
        )
        is ContentBlock.SummaryBlock -> SummaryCard(
            block = block,
            onToggle = { onToggleSummary(msgId, block.blockId) },
            modifier = Modifier
                .fillMaxWidth()
                .alpha(alpha),
        )
        is ContentBlock.ImageBlock -> ImageAttachmentBlock(
            block = block,
            modifier = Modifier.alpha(alpha),
        )
        is ContentBlock.FileBlock -> FileAttachmentBlock(
            block = block,
            modifier = Modifier.alpha(alpha),
            maxWidth = 320.dp,
        )
        is ContentBlock.ThinkingBlock,
        is ContentBlock.ToolBlock -> {
            // Execution blocks are rendered through ExecutionGroupCard.
        }
    }
}
```

This keeps normal blocks exactly on their existing rendering path and prevents duplicating old `when` branches inside the render item loop.

- [ ] **Step 3: Preserve fade-in behavior for new streaming blocks**

Keep the existing `knownIds` / `alphaMap` logic unchanged. Execution groups should not add a second group-level fade in the first version; each newly arriving block already records its own alpha. If group-level fade is desired later, add it explicitly after visual verification.

- [ ] **Step 4: Compile**

Run:

```bash
./gradlew :app:compileDebugKotlin
```

Expected: PASS.

- [ ] **Step 5: Run focused unit tests**

Run:

```bash
./gradlew :app:testDebugUnitTest --tests "com.sebastian.android.ui.chat.*"
```

Expected: PASS.

- [ ] **Step 6: Commit integration**

```bash
git add ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/StreamingMessage.kt
git commit -m "feat(android): 接入执行步骤外层折叠渲染" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

## Task 5: Update Android README Navigation

**Files:**
- Modify: `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/README.md`
- Modify: `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/README.md`
- Optional Modify: `ui/mobile-android/README.md`

- [ ] **Step 1: Update chat module directory structure**

In `ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/README.md`, add:

```text
├── ExecutionGroupCard.kt      # 连续 thinking/tool blocks 的外层折叠容器（竖胶囊步骤条）
├── ExecutionRenderItems.kt    # 消息 block → 渲染项 / 执行组的纯分组逻辑
```

- [ ] **Step 2: Update StreamingMessage section**

In the `StreamingMessage` section, add a short paragraph:

```markdown
连续的 `ThinkingBlock` / `ToolBlock` 在渲染前会先由 `ExecutionRenderItems` 聚合为外层执行组；折叠态显示单行横向滑动的竖胶囊步骤条，展开后复用 `ThinkingCard` / `ToolCallCard` 渲染原始明细。分组只发生在 UI 层，不改变 SSE、REST 或持久化模型。
```

- [ ] **Step 3: Update modification navigation**

In `chat/README.md`, update the message rendering row:

```markdown
| 改消息渲染分发逻辑 / 执行步骤外层折叠 | `StreamingMessage.kt`、`ExecutionRenderItems.kt`、`ExecutionGroupCard.kt` |
```

In `ui/README.md`, update the message rendering row:

```markdown
| 改消息渲染（文本/思考/工具调用/执行步骤折叠） | `chat/StreamingMessage.kt`、`chat/ExecutionRenderItems.kt`、`chat/ExecutionGroupCard.kt`、`chat/ThinkingCard.kt`、`chat/ToolCallCard.kt` |
```

If `ui/mobile-android/README.md` has a matching row, update it similarly.

- [ ] **Step 4: Commit docs**

```bash
git add ui/mobile-android/app/src/main/java/com/sebastian/android/ui/chat/README.md ui/mobile-android/app/src/main/java/com/sebastian/android/ui/README.md ui/mobile-android/README.md
git commit -m "docs(android): 更新执行步骤折叠导航" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

If `ui/mobile-android/README.md` did not change, omit it from `git add`.

## Task 6: Final Verification

**Files:**
- Verify all changed Android files.
- Verify docs/spec/plan files if committing them in this branch.

- [ ] **Step 1: Run Android chat tests**

Run:

```bash
./gradlew :app:testDebugUnitTest --tests "com.sebastian.android.ui.chat.*"
```

Expected: PASS.

- [ ] **Step 2: Run Android Kotlin compile**

Run:

```bash
./gradlew :app:compileDebugKotlin
```

Expected: PASS.

- [ ] **Step 3: Run full Android unit tests if time allows**

Run:

```bash
./gradlew :app:testDebugUnitTest
```

Expected: PASS.

- [ ] **Step 4: Manual UI verification**

Run the app and trigger a long assistant task with several thinking/tool blocks.

Verify:

- Consecutive thinking/tool blocks render as one collapsed execution group.
- The capsule row stays one line.
- Capsules append from left to right.
- Current running step is green and pulsing.
- Failed step is red.
- No future gray placeholders appear.
- Latest capsule remains fully visible after overflow.
- Horizontal swipe can reveal older capsules.
- Expanding the group shows original `ThinkingCard` and `ToolCallCard` details.
- Text/image/file/summary blocks still render outside execution groups.

- [ ] **Step 5: Rebuild graphify code graph after code modifications**

From repo root:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: completes without error. If `graphify` is unavailable in the local environment, record the failure and do not block Android verification on it.

- [ ] **Step 6: Commit spec and plan if not already committed**

```bash
git add docs/superpowers/specs/2026-05-09-android-execution-block-collapse-design.md docs/superpowers/plans/2026-05-09-android-execution-block-collapse-implementation.md
git commit -m "docs(android): 设计执行步骤外层折叠方案" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

Skip if these docs were intentionally left uncommitted for review.
