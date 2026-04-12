package com.sebastian.android.ui.chat

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sebastian.android.data.model.Session

@Composable
fun SessionPanel(
    sessions: List<Session>,
    activeSessionId: String?,
    onSessionClick: (Session) -> Unit,
    onNewSession: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToSubAgents: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        // Plan 3 填充：会话列表 + 导航入口
        Text("SessionPanel - TODO")
    }
}
