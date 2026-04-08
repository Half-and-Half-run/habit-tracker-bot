package com.example.habit_locker

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class MainApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // flutter_background_service のデフォルトチャンネルID "FOREGROUND_DEFAULT" を
        // プロセス起動時に確実に作成しておく（Bad notification クラッシュ対策）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "FOREGROUND_DEFAULT",
                "Background Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Habit Locker background monitoring service"
            }
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }
    }
}
