package com.sebastian.android.ui.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.navigation.NavController
import com.sebastian.android.ui.navigation.Route

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(navController: NavController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("设置") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            SettingsItem(
                title = "连接与账户",
                subtitle = "服务器地址、登录状态",
                onClick = { navController.navigate(Route.SettingsConnection) { launchSingleTop = true } },
            )
            HorizontalDivider()
            SettingsItem(
                title = "模型与 Provider",
                subtitle = "LLM Provider 管理",
                onClick = { navController.navigate(Route.SettingsProviders) { launchSingleTop = true } },
            )
            HorizontalDivider()
            SettingsItem(
                title = "Agent LLM Bindings",
                subtitle = "为每个 Agent 选择 Provider",
                onClick = { navController.navigate(Route.SettingsAgentBindings) { launchSingleTop = true } },
            )
            HorizontalDivider()
            SettingsItem(
                title = "外观",
                subtitle = "主题模式",
                onClick = { navController.navigate(Route.SettingsAppearance) { launchSingleTop = true } },
            )
            HorizontalDivider()
            SettingsItem(
                title = "调试日志",
                subtitle = "LLM Stream、SSE 日志开关",
                onClick = { navController.navigate(Route.SettingsDebugLogging) { launchSingleTop = true } },
            )
            HorizontalDivider()
            NotificationPermissionRow()
        }
    }
}

@Composable
private fun NotificationPermissionRow() {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var enabled by remember(context) {
        mutableStateOf(NotificationManagerCompat.from(context).areNotificationsEnabled())
    }
    // 从系统设置页回到前台时重新读权限状态，避免陈旧快照
    DisposableEffect(lifecycleOwner, context) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                enabled = NotificationManagerCompat.from(context).areNotificationsEnabled()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    if (enabled) return

    ListItem(
        headlineContent = { Text("通知权限未开启") },
        supportingContent = { Text("开启后 Sebastian 离线时可通知审批与任务完成") },
        trailingContent = {
            TextButton(onClick = {
                val intent = android.content.Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, context.packageName)
                context.startActivity(intent)
            }) { Text("去设置") }
        },
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun SettingsItem(
    title: String,
    subtitle: String,
    onClick: () -> Unit,
) {
    ListItem(
        headlineContent = { Text(title) },
        supportingContent = { Text(subtitle) },
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    )
}
