package com.tiktokforbot.admin.service

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.tiktokforbot.admin.MainActivity
import com.tiktokforbot.admin.R

object NotificationHelper {

    // أنواع القنوات
    const val CHANNEL_ALERTS = "alerts"       // تنبيهات هامة
    const val CHANNEL_UPDATES = "updates"      // تحديثات عامة
    const val CHANNEL_ERRORS = "errors"        // أخطاء
    const val CHANNEL_USERS = "users"          // مستخدمين جدد

    private var notificationId = 1000

    fun initChannels(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            val channels = listOf(
                NotificationChannel(
                    CHANNEL_ALERTS,
                    "تنبيهات هامة",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "تنبيهات فورية للتحديثات الهامة"
                    enableVibration(true)
                },
                NotificationChannel(
                    CHANNEL_UPDATES,
                    "تحديثات عامة",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "تحديثات حالة البوت والإحصائيات"
                },
                NotificationChannel(
                    CHANNEL_ERRORS,
                    "أخطاء",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "تنبيهات عند حدوث أخطاء في النظام"
                    enableVibration(true)
                },
                NotificationChannel(
                    CHANNEL_USERS,
                    "مستخدمين جدد",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "تنبيه عند تسجيل مستخدم جديد"
                }
            )
            manager.createNotificationChannels(channels)
        }
    }

    /**
     * إرسال إشعار للمستخدم
     */
    fun show(
        context: Context,
        channelId: String,
        title: String,
        message: String,
        bigText: String? = null,
        autoCancel: Boolean = true
    ) {
        // التحقق من الصلاحية (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
                return // لا صلاحية لإرسال الإشعارات
            }
        }

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }

        val pendingIntent = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(message)
            .setPriority(
                when (channelId) {
                    CHANNEL_ALERTS, CHANNEL_ERRORS -> NotificationCompat.PRIORITY_HIGH
                    else -> NotificationCompat.PRIORITY_DEFAULT
                }
            )
            .setAutoCancel(autoCancel)
            .setContentIntent(pendingIntent)

        if (bigText != null) {
            builder.setStyle(NotificationCompat.BigTextStyle().bigText(bigText))
        }

        try {
            NotificationManagerCompat.from(context).notify(notificationId++, builder.build())
        } catch (e: SecurityException) {
            // لا صلاحية
        }
    }

    // ========== دوال مساعدة سريعة ==========

    fun alert(context: Context, title: String, message: String) {
        show(context, CHANNEL_ALERTS, title, message)
    }

    fun error(context: Context, title: String, message: String) {
        show(context, CHANNEL_ERRORS, "❌ $title", message)
    }

    fun newUser(context: Context, userName: String) {
        show(
            context, CHANNEL_USERS,
            "👤 مستخدم جديد",
            "$userName انضم للتو",
            bigText = "مستخدم جديد سجل في البوت: $userName"
        )
    }

    fun botStatusChanged(context: Context, running: Boolean) {
        val (title, msg) = if (running) {
            "🟢 تم تشغيل البوت" to "البوت يعمل الآن ويستقبل الطلبات"
        } else {
            "🔴 تم إيقاف البوت" to "البوت متوقف حالياً ولا يستقبل طلبات"
        }
        show(context, CHANNEL_UPDATES, title, msg)
    }

    fun serverError(context: Context, endpoint: String, code: Int) {
        show(
            context, CHANNEL_ERRORS,
            "⚠️ خطأ في السيرفر",
            "فشل في $endpoint (كود $code)",
            bigText = "حدث خطأ في الاتصال بالسيرفر:\nالمسار: $endpoint\nكود الخطأ: $code\nالوقت: ${System.currentTimeMillis()}"
        )
    }

    fun criticalError(context: Context, message: String) {
        show(
            context, CHANNEL_ERRORS,
            "🚨 خطأ حرج",
            message,
            bigText = "حدث خطأ حرج يتطلب انتباهك:\n$message"
        )
    }
}
