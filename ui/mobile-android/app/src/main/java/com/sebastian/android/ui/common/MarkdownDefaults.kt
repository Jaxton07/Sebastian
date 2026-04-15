package com.sebastian.android.ui.common

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.sp
import com.mikepenz.markdown.compose.components.MarkdownComponents
import com.mikepenz.markdown.compose.components.markdownComponents
import com.mikepenz.markdown.compose.elements.MarkdownHighlightedCodeBlock
import com.mikepenz.markdown.compose.elements.MarkdownHighlightedCodeFence
import com.mikepenz.markdown.m3.markdownColor
import com.mikepenz.markdown.m3.markdownTypography
import com.mikepenz.markdown.model.MarkdownColors
import com.mikepenz.markdown.model.MarkdownTypography
import dev.snipme.highlights.Highlights
import dev.snipme.highlights.model.SyntaxThemes

object MarkdownDefaults {

    @Composable
    fun colors(): MarkdownColors = markdownColor(
        text = MaterialTheme.colorScheme.onSurface,
        codeBackground = MaterialTheme.colorScheme.surfaceVariant,
        inlineCodeBackground = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f),
        dividerColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.12f),
    )

    @Composable
    fun typography(): MarkdownTypography = markdownTypography(
        h1 = MaterialTheme.typography.headlineMedium,
        h2 = MaterialTheme.typography.titleLarge,
        h3 = MaterialTheme.typography.titleMedium,
        h4 = MaterialTheme.typography.titleSmall,
        h5 = MaterialTheme.typography.bodyLarge,
        h6 = MaterialTheme.typography.bodyMedium,
        text = MaterialTheme.typography.bodyLarge,
        code = TextStyle(
            fontFamily = FontFamily.Monospace,
            fontSize = 13.sp,
            lineHeight = 20.sp,
        ),
        inlineCode = MaterialTheme.typography.bodyMedium.copy(
            fontFamily = FontFamily.Monospace,
        ),
    )

    @Composable
    fun components(): MarkdownComponents {
        val highlightsBuilder = remember {
            Highlights.Builder().theme(SyntaxThemes.atom(darkMode = true))
        }
        return markdownComponents(
            codeBlock = {
                MarkdownHighlightedCodeBlock(
                    content = it.content,
                    node = it.node,
                    highlightsBuilder = highlightsBuilder,
                    showHeader = true,
                )
            },
            codeFence = {
                MarkdownHighlightedCodeFence(
                    content = it.content,
                    node = it.node,
                    highlightsBuilder = highlightsBuilder,
                    showHeader = true,
                )
            },
        )
    }
}
