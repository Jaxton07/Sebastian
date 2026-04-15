package com.sebastian.android.notification

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.content.getSystemService

object NotificationChannels {
    const val APPROVAL = "approval"
    const val TASK_PROGRESS = "task_progress"

    fun registerAll(context: Context) {
        val manager = context.getSystemService<NotificationManager>() ?: return
        manager.createNotificationChannel(
            NotificationChannel(
                APPROVAL,
                "审批请求",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Agent 需要你批准或拒绝的工具调用"
            }
        )
        manager.createNotificationChannel(
            NotificationChannel(
                TASK_PROGRESS,
                "任务进度",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "子代理完成或失败的状态"
            }
        )
    }
}
