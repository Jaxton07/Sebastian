package com.sebastian.android.ui.common

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.sebastian.android.ui.theme.SwitchCheckedDark
import com.sebastian.android.ui.theme.SwitchCheckedLight

/**
 * 苹果风格绿色开关，签名与 Material3 Switch 一致。
 * 跟随系统 dark/light 模式自动切换色值。
 */
@Composable
fun SebastianSwitch(
    checked: Boolean,
    onCheckedChange: ((Boolean) -> Unit)?,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val checkedTrack = if (isSystemInDarkTheme()) SwitchCheckedDark else SwitchCheckedLight
    Switch(
        checked = checked,
        onCheckedChange = onCheckedChange,
        modifier = modifier,
        enabled = enabled,
        colors = SwitchDefaults.colors(
            checkedThumbColor = Color.White,
            checkedTrackColor = checkedTrack,
            checkedBorderColor = Color.Transparent,
        ),
    )
}
