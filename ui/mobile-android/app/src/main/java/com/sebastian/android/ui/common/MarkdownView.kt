package com.sebastian.android.ui.common

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.mikepenz.markdown.m3.Markdown
import com.mikepenz.markdown.model.rememberMarkdownState

/**
 * 渲染 Markdown 字符串。
 * 底层使用 multiplatform-markdown-renderer（纯 Compose，无 AndroidView 包装）。
 * - rememberMarkdownState(retainState = true)：流式更新时保留旧内容，不闪白屏/loading
 * - 样式配置统一在 [MarkdownDefaults] 中定义
 */
@Composable
fun MarkdownView(
    text: String,
    modifier: Modifier = Modifier,
) {
    val markdownState = rememberMarkdownState(text, retainState = true)
    Markdown(
        markdownState = markdownState,
        modifier = modifier,
        colors = MarkdownDefaults.colors(),
        typography = MarkdownDefaults.typography(),
        components = MarkdownDefaults.components(),
    )
}
