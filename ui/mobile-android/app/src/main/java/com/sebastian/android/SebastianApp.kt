package com.sebastian.android

import android.app.Application
import com.sebastian.android.notification.NotificationChannels
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class SebastianApp : Application() {
    override fun onCreate() {
        super.onCreate()
        NotificationChannels.registerAll(this)
    }
}
