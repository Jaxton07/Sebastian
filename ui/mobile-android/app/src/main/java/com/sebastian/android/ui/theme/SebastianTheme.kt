package com.sebastian.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = PrimaryLight,
    onPrimary = OnPrimaryLight,
    surface = SurfaceLight,
    onSurface = OnSurfaceLight,
    background = BackgroundLight,
    surfaceVariant = SurfaceVariantLight,
    onSurfaceVariant = OnSurfaceVariantLight,
)

private val DarkColors = darkColorScheme(
    primary = PrimaryDark,
    onPrimary = OnPrimaryDark,
    surface = SurfaceDark,
    onSurface = OnSurfaceDark,
    background = BackgroundDark,
    surfaceVariant = SurfaceVariantDark,
    onSurfaceVariant = OnSurfaceVariantDark,
)

/**
 * @param themeMode "system" | "light" | "dark"
 */
@Composable
fun SebastianTheme(
    themeMode: String = "system",
    content: @Composable () -> Unit,
) {
    val darkTheme = when (themeMode) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }

    val colorScheme = if (darkTheme) DarkColors else LightColors

    MaterialTheme(
        colorScheme = colorScheme,
        content = content,
    )
}
