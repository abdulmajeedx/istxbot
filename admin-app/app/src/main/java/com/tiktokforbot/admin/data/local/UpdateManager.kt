package com.tiktokforbot.admin.data.local

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Environment
import androidx.core.content.FileProvider
import com.tiktokforbot.admin.BuildConfig
import com.tiktokforbot.admin.data.model.UpdateInfo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream

object UpdateManager {

    private var downloadFile: File? = null

    fun hasUpdate(updateInfo: UpdateInfo): Boolean {
        return updateInfo.versionCode > BuildConfig.VERSION_CODE
    }

    /**
     * تنزيل ملف APK باستخدام DownloadManager (يعمل في الخلفية ويظهر إشعار)
     */
    fun downloadWithSystemManager(context: Context, updateInfo: UpdateInfo): Long {
        val url = updateInfo.downloadUrl.ifBlank {
            "${BuildConfig.BASE_URL}app-debug.apk"
        }
        val fileName = "TikTokForBot_v${updateInfo.versionName}.apk"

        // حذف الملف القديم إذا وجد
        val dir = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: context.filesDir
        val file = File(dir, fileName)
        if (file.exists()) file.delete()
        downloadFile = file

        val request = DownloadManager.Request(Uri.parse(url)).apply {
            setTitle("تحديث TikTokForBot")
            setDescription("جارٍ تنزيل النسخة ${updateInfo.versionName}...")
            setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            setDestinationUri(Uri.fromFile(file))
            setAllowedOverMetered(true)
            setAllowedOverRoaming(true)
        }

        val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        return manager.enqueue(request)
    }

    /**
     * تثبيت ملف APK تم تنزيله
     */
    fun installApk(context: Context, file: File) {
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )

        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        }

        try {
            context.startActivity(intent)
        } catch (e: Exception) {
            AppLogger.log(AppLogger.Level.ERROR, "UpdateManager", "فشل تثبيت التطبيق: ${e.message}")
        }
    }

    /**
     * تسجيل مستقبل للاستماع لاكتمال التنزيل والتثبيت التلقائي
     */
    fun registerDownloadReceiver(
        context: Context,
        downloadId: Long,
        onComplete: () -> Unit
    ): BroadcastReceiver {
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                val id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1)
                if (id == downloadId) {
                    downloadFile?.let { file ->
                        if (file.exists()) {
                            AppLogger.event("تحديث", "تم تنزيل النسخة الجديدة بنجاح")
                            installApk(context, file)
                            onComplete()
                        }
                    }
                }
            }
        }
        // API guard: RECEIVER_NOT_EXPORTED موجود فقط في API 33+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(
                receiver,
                IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE),
                Context.RECEIVER_NOT_EXPORTED
            )
        } else {
            @Suppress("DEPRECATION")
            context.registerReceiver(
                receiver,
                IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE)
            )
        }
        return receiver
    }

    fun getFilePath(): File? = downloadFile
}
