package com.tiktokforbot.admin.data.local

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileWriter
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.*

/**
 * نظام تسجيل الأخطاء والأحداث تلقائياً.
 * يكتب السجلات في ملف داخل التخزين الداخلي للتطبيق.
 *
 * المسار: /data/data/com.tiktokforbot.admin/files/logs/app.log
 */
object AppLogger {

    private const val LOG_DIR = "logs"
    private const val LOG_FILE = "app.log"
    private const val MAX_LOG_SIZE_MB = 5
    private const val MAX_BACKUP_FILES = 3

    private var logFile: File? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US)

    enum class Level(val emoji: String, val label: String) {
        INFO("📘", "INFO"),
        WARN("⚠️", "WARN"),
        ERROR("❌", "ERROR"),
        EVENT("🟢", "EVENT"),
        API("🌐", "API"),
        AUTH("🔐", "AUTH"),
        UI("📱", "UI")
    }

    fun init(context: Context) {
        if (logFile != null) return
        val logDir = File(context.filesDir, LOG_DIR)
        if (!logDir.exists()) logDir.mkdirs()
        logFile = File(logDir, LOG_FILE)
        log(Level.INFO, "Logger", "تم تهيئة نظام التسجيل — ${logFile!!.absolutePath}")
        log(Level.INFO, "Logger", "إصدار التطبيق: ${getAppVersion(context)}")
    }

    fun log(level: Level, tag: String, message: String, throwable: Throwable? = null) {
        scope.launch {
            try {
                val file = logFile ?: return@launch
                rotateIfNeeded(file)
                val timestamp = dateFormat.format(Date())
                val throwableStr = throwable?.let {
                    val sw = StringWriter()
                    it.printStackTrace(PrintWriter(sw))
                    "\n${sw.toString()}"
                } ?: ""
                val line = "${level.emoji} [$timestamp] [${level.label}] [$tag] $message$throwableStr\n"
                FileWriter(file, true).use { it.write(line) }
            } catch (_: Exception) {
                // لا يمكن التسجيل — تجاهل بهدوء
            }
        }
    }

    fun event(eventName: String, details: String = "") {
        log(Level.EVENT, "UserEvent", "$eventName ${if (details.isNotEmpty()) "| $details" else ""}")
    }

    fun apiError(endpoint: String, code: Int, errorBody: String?) {
        log(Level.API, "API", "$endpoint → HTTP $code ${errorBody?.take(200) ?: ""}")
    }

    fun crash(throwable: Throwable) {
        log(Level.ERROR, "CRASH", "تطبيق انهار!", throwable)
    }

    fun getLogFilePath(): String {
        return logFile?.absolutePath ?: "لم يتم التهيئة بعد"
    }

    fun getLogContent(maxLines: Int = 500): String {
        val file = logFile ?: return "لم يتم التهيئة"
        return try {
            file.readLines().takeLast(maxLines).joinToString("\n")
        } catch (e: Exception) {
            "خطأ في قراءة السجل: ${e.message}"
        }
    }

    fun getLogSizeInfo(): String {
        val file = logFile ?: return "N/A"
        val bytes = file.length()
        return when {
            bytes < 1024 -> "$bytes B"
            bytes < 1024 * 1024 -> "${bytes / 1024} KB"
            else -> "${"%.1f".format(bytes.toDouble() / (1024 * 1024))} MB"
        }
    }

    fun clearLogs() {
        scope.launch {
            try {
                logFile?.writeText("")
                log(Level.INFO, "Logger", "تم مسح السجلات")
            } catch (_: Exception) {}
        }
    }

    private fun rotateIfNeeded(file: File) {
        val maxBytes = MAX_LOG_SIZE_MB.toLong() * 1024 * 1024
        if (file.length() < maxBytes) return
        // تدوير الملفات القديمة
        for (i in MAX_BACKUP_FILES downTo 1) {
            val oldFile = File(file.parent, "${file.name}.$i")
            val newFile = File(file.parent, "${file.name}.${i + 1}")
            if (oldFile.exists()) {
                if (i == MAX_BACKUP_FILES) oldFile.delete()
                else oldFile.renameTo(newFile)
            }
        }
        file.renameTo(File(file.parent, "${file.name}.1"))
        file.createNewFile()
    }

    private fun getAppVersion(context: Context): String {
        return try {
            val info = context.packageManager.getPackageInfo(context.packageName, 0)
            info.versionName ?: "?"
        } catch (_: Exception) { "?" }
    }
}
