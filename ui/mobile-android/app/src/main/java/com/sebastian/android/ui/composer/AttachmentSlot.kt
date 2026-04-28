package com.sebastian.android.ui.composer

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

@Composable
fun AttachmentSlot(
    onImageClick: () -> Unit,
    onFileClick: () -> Unit,
    enabled: Boolean = true,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val iconTint = if (isSystemInDarkTheme()) Color(0xFF9E9E9E) else Color.Black

    Box(modifier) {
        IconButton(
            onClick = { expanded = true },
            enabled = enabled,
        ) {
            Icon(Icons.Default.AttachFile, contentDescription = "附件", tint = iconTint)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("图片") },
                onClick = { expanded = false; onImageClick() },
            )
            DropdownMenuItem(
                text = { Text("文件") },
                onClick = { expanded = false; onFileClick() },
            )
        }
    }
}
