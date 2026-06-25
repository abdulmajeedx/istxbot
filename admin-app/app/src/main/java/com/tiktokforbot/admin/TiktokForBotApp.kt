package com.tiktokforbot.admin

import android.app.Application
import com.tiktokforbot.admin.data.local.AppLogger
import com.tiktokforbot.admin.data.local.SessionManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch

class TiktokForBotApp : Application() {

    lateinit var sessionManager: SessionManager
        private set

    override fun onCreate() {
        super.onCreate()
        sessionManager = SessionManager(this)
        AppLogger.init(this)

        // معالج الأعطال العام — يسجل أي انهيار قبل موت التطبيق
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            AppLogger.crash(throwable)
            // حفظ الكراش في DataStore — fire-and-forget بدون runBlocking
            val crashMsg = "${throwable.javaClass.simpleName}: ${throwable.message}\n${throwable.stackTrace.take(5).joinToString("\n") { "  at ${it.className}.${it.methodName}(${it.fileName}:${it.lineNumber})" }}"
            kotlinx.coroutines.GlobalScope.launch(kotlinx.coroutines.Dispatchers.IO) {
                runCatching { sessionManager.saveCrash(crashMsg) }
            }
            defaultHandler?.uncaughtException(thread, throwable)
        }
    }
}
