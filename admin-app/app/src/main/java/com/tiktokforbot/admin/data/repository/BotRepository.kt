package com.tiktokforbot.admin.data.repository

import com.tiktokforbot.admin.data.api.RetrofitClient
import com.tiktokforbot.admin.data.local.AppLogger
import com.tiktokforbot.admin.data.model.*
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive

class BotRepository {

    private val api = RetrofitClient.apiService
    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    // ==================== معالجة الأخطاء المركزية ====================

    /**
     * يستخرج رسالة خطأ بشرية من استجابة HTTP.
     * يتعامل مع JSON (من API حقيقي) و HTML (من nginx/apache 404/502).
     * لا يرجع أبداً HTML خام للمستخدم.
     */
    private fun parseErrorMessage(errorBody: String?, code: Int): String {
        // لا يوجد جسم في الاستجابة
        if (errorBody.isNullOrBlank()) {
            return when (code) {
                404 -> "المسار غير موجود (404) — تأكد من إعدادات السيرفر"
                500 -> "خطأ داخلي في السيرفر (500)"
                502 -> "بوابة غير صالحة (502) — السيرفر الخلفي معطل"
                503 -> "الخدمة غير متاحة مؤقتاً (503)"
                401 -> "غير مصرح — تأكد من اسم المستخدم وكلمة المرور"
                403 -> "محظور — لا تملك صلاحية الوصول"
                429 -> "طلبات كثيرة — حاول مرة أخرى لاحقاً"
                else -> "خطأ في السيرفر (كود $code)"
            }
        }

        // اكتشاف HTML — إذا كان النص يبدأ بوسم HTML
        val trimmed = errorBody.trimStart()
        if (trimmed.startsWith("<") || trimmed.startsWith("<!DOCTYPE", ignoreCase = true)) {
            return when (code) {
                404 -> "المسار غير موجود (404)\nتأكد من أن السيرفر يعمل وأن الرابط صحيح"
                500 -> "خطأ داخلي في السيرفر (500)\nراجع سجلات السيرفر للتفاصيل"
                502 -> "السيرفر الخلفي معطل (502 Bad Gateway)"
                503 -> "الخدمة غير متاحة (503)\nالسيرفر قيد الصيانة أو محمّل أكثر من طاقته"
                else -> "السيرفر أرجع خطأ (كود $code)\nقد يكون السيرفر غير مهيأ بشكل صحيح"
            }
        }

        // محاولة تحليل JSON
        return try {
            val obj = json.decodeFromString<JsonObject>(errorBody)
            obj["message"]?.jsonPrimitive?.content
                ?: obj["error"]?.jsonPrimitive?.content
                ?: obj["detail"]?.jsonPrimitive?.content
                ?: when (code) {
                    404 -> "المسار غير موجود (404)"
                    500 -> "خطأ داخلي في السيرفر (500)"
                    422 -> "بيانات غير صالحة (422)"
                    else -> "خطأ في السيرفر (كود $code)"
                }
        } catch (e: Exception) {
            // لا يمكن تحليلها — إما نص عادي أو تنسيق غير معروف
            // نعرض أول 100 حرف فقط مع رمز الخطأ
            val snippet = errorBody.take(100).replace("\n", " ")
            "خطأ في السيرفر (كود $code): $snippet"
        }
    }

    /**
     * يسجل الخطأ في AppLogger ويستخرج رسالة بشرية.
     * تستدعي errorBody.string() مرة واحدة فقط.
     */
    private fun handleError(endpoint: String, code: Int, errorBody: okhttp3.ResponseBody?): String {
        val body = errorBody?.string()
        logApiError(endpoint, code, body)
        return parseErrorMessage(body, code)
    }

    private fun logApiError(endpoint: String, code: Int, errorBody: String?) {
        AppLogger.apiError(endpoint, code, errorBody)
    }

    private fun logEvent(event: String, details: String = "") {
        AppLogger.event(event, details)
    }

    // ==================== المصادقة ====================
    suspend fun login(username: String, password: String): Result<LoginResponse> = runCatching {
        val response = api.login(LoginRequest(username, password))
        if (response.isSuccessful) {
            logEvent("تسجيل الدخول", "المستخدم: $username")
            response.body() ?: throw Exception("استجابة فارغة من السيرفر")
        } else {
            throw Exception(handleError("POST api/login", response.code(), response.errorBody()))
        }
    }

    suspend fun verify2fa(code: String): Result<Verify2faResponse> = runCatching {
        val response = api.verify2fa(Verify2faRequest(code))
        if (response.isSuccessful) {
            logEvent("تحقق 2FA", "تم بنجاح")
            response.body() ?: throw Exception("استجابة فارغة من السيرفر")
        } else {
            throw Exception(handleError("POST api/verify-2fa", response.code(), response.errorBody()))
        }
    }

    suspend fun logout() {
        runCatching { api.logout() }
        RetrofitClient.clearSession()
    }

    // ==================== حالة البوت ====================
    suspend fun getStatus(): Result<BotStatusResponse> = runCatching {
        val response = api.getStatus()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/status", response.code(), response.errorBody()))
    }

    suspend fun startBot(): Result<GenericResponse> = runCatching {
        logEvent("تشغيل البوت")
        val response = api.startBot()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/start", response.code(), response.errorBody()))
    }

    suspend fun stopBot(): Result<GenericResponse> = runCatching {
        logEvent("إيقاف البوت")
        val response = api.stopBot()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/stop", response.code(), response.errorBody()))
    }

    suspend fun restartBot(): Result<GenericResponse> = runCatching {
        logEvent("إعادة تشغيل البوت")
        val response = api.restartBot()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/restart", response.code(), response.errorBody()))
    }

    // ==================== الإحصائيات ====================
    suspend fun getStats(): Result<StatsResponse> = runCatching {
        val response = api.getStats()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/stats", response.code(), response.errorBody()))
    }

    suspend fun getAnalytics(): Result<AnalyticsResponse> = runCatching {
        val response = api.getAnalytics()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/analytics", response.code(), response.errorBody()))
    }

    // ==================== الإعدادات ====================
    suspend fun getGeneralSettings(): Result<GeneralSettings> = runCatching {
        val response = api.getGeneralSettings()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/settings", response.code(), response.errorBody()))
    }

    suspend fun updateGeneralSettings(settings: UpdateGeneralSettingsRequest): Result<SettingsResponse> = runCatching {
        val response = api.updateGeneralSettings(settings)
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/settings", response.code(), response.errorBody()))
    }

    suspend fun getPlatformSettings(): Result<PlatformSettingsResponse> = runCatching {
        val response = api.getPlatformSettings()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/settings/platforms", response.code(), response.errorBody()))
    }

    suspend fun updatePlatformSettings(platforms: Map<String, Map<String, Any>>): Result<SettingsResponse> = runCatching {
        val response = api.updatePlatformSettings(platforms)
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/settings/platforms", response.code(), response.errorBody()))
    }

    suspend fun getTierLimits(): Result<TierLimits> = runCatching {
        val response = api.getTierLimits()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/tier-limits", response.code(), response.errorBody()))
    }

    suspend fun updateTierLimits(limits: TierLimits): Result<SettingsResponse> = runCatching {
        val response = api.updateTierLimits(limits)
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/tier-limits", response.code(), response.errorBody()))
    }

    // ==================== المستخدمين ====================
    suspend fun getUsers(): Result<List<BotUser>> = runCatching {
        val response = api.getUsers()
        if (response.isSuccessful) response.body() ?: emptyList()
        else throw Exception(handleError("GET api/users", response.code(), response.errorBody()))
    }

    suspend fun searchUsers(query: String): Result<List<BotUser>> = runCatching {
        val response = api.searchUsers(query)
        if (response.isSuccessful) response.body() ?: emptyList()
        else throw Exception(handleError("GET api/users/search?q=$query", response.code(), response.errorBody()))
    }

    suspend fun banUser(userId: Int): Result<GenericResponse> = runCatching {
        logEvent("حظر مستخدم", "ID: $userId")
        val response = api.banUser(userId)
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/users/$userId/ban", response.code(), response.errorBody()))
    }

    suspend fun unbanUser(userId: Int): Result<GenericResponse> = runCatching {
        logEvent("إلغاء حظر مستخدم", "ID: $userId")
        val response = api.unbanUser(userId)
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/users/$userId/unban", response.code(), response.errorBody()))
    }

    suspend fun getOnlineUsers(): Result<OnlineUsersResponse> = runCatching {
        val response = api.getOnlineUsers()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/online-users", response.code(), response.errorBody()))
    }

    // ==================== الإدارة ====================
    suspend fun getAdminInfo(): Result<AdminInfoResponse> = runCatching {
        val response = api.getAdminInfo()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد بيانات")
        else throw Exception(handleError("GET api/admin/info", response.code(), response.errorBody()))
    }

    suspend fun changePassword(currentPassword: String, newPassword: String): Result<GenericResponse> = runCatching {
        val response = api.changePassword(ChangePasswordRequest(currentPassword, newPassword))
        if (response.isSuccessful) {
            logEvent("تغيير كلمة المرور", "تم بنجاح")
            response.body() ?: throw Exception("لا توجد استجابة")
        }
        else throw Exception(handleError("POST api/admin/change-password", response.code(), response.errorBody()))
    }

    suspend fun broadcastMessage(message: String): Result<GenericResponse> = runCatching {
        logEvent("بث رسالة", "طول: ${message.length} حرف")
        val response = api.broadcastMessage(BroadcastRequest(message))
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/admin/broadcast", response.code(), response.errorBody()))
    }

    suspend fun sendMessageToUser(userId: Int, message: String): Result<GenericResponse> = runCatching {
        val response = api.sendMessage(SendMessageRequest(userId, message))
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/admin/send-message", response.code(), response.errorBody()))
    }

    suspend fun restartServer(): Result<GenericResponse> = runCatching {
        logEvent("إعادة تشغيل السيرفر")
        val response = api.restartServer()
        if (response.isSuccessful) response.body() ?: throw Exception("لا توجد استجابة")
        else throw Exception(handleError("POST api/admin/restart-server", response.code(), response.errorBody()))
    }

    // ==================== السجلات ====================
    suspend fun getLogs(count: Int = 100): Result<List<Map<String, String>>> = runCatching {
        val response = api.getLogs(n = count)
        if (response.isSuccessful) {
            response.body()?.map { obj ->
                obj.mapValues { it.value.toString().trim('"') }
            } ?: emptyList()
        } else throw Exception(handleError("GET api/logs", response.code(), response.errorBody()))
    }

    suspend fun getLoginHistory(): Result<Map<String, String>> = runCatching {
        val response = api.getLoginHistory()
        if (response.isSuccessful) {
            response.body()?.mapValues { it.value.toString().trim('"') } ?: emptyMap()
        } else throw Exception(handleError("GET api/login-history", response.code(), response.errorBody()))
    }

    // ==================== التحديث ====================
    suspend fun checkUpdate(): Result<UpdateInfo> = runCatching {
        val client = okhttp3.OkHttpClient()
        val request = okhttp3.Request.Builder()
            .url("https://inspiredownloader.com/app/version.json")
            .build()
        val response = client.newCall(request).execute()
        val body = response.body?.string() ?: throw Exception("استجابة فارغة")
        json.decodeFromString<UpdateInfo>(body)
    }
}
