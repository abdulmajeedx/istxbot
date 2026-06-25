package com.tiktokforbot.admin.data.api

import com.tiktokforbot.admin.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface BotApiService {

    // ==================== المصادقة ====================
    @POST("api/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @POST("api/verify-2fa")
    suspend fun verify2fa(@Body request: Verify2faRequest): Response<Verify2faResponse>

    @POST("api/logout")
    suspend fun logout(): Response<GenericResponse>

    // ==================== حالة البوت ====================
    @GET("api/status")
    suspend fun getStatus(): Response<BotStatusResponse>

    @POST("api/start")
    suspend fun startBot(): Response<GenericResponse>

    @POST("api/stop")
    suspend fun stopBot(): Response<GenericResponse>

    @POST("api/restart")
    suspend fun restartBot(): Response<GenericResponse>

    // ==================== الإحصائيات ====================
    @GET("api/stats")
    suspend fun getStats(): Response<StatsResponse>

    @GET("api/analytics")
    suspend fun getAnalytics(): Response<AnalyticsResponse>

    // ==================== الإعدادات ====================
    @GET("api/get_settings")
    suspend fun getPublicSettings(): Response<Map<String, @JvmSuppressWildcards Any>>

    @GET("api/settings")
    suspend fun getSettings(): Response<GeneralSettings>

    @POST("api/settings")
    suspend fun updateSettings(@Body settings: UpdateGeneralSettingsRequest): Response<SettingsResponse>

    @GET("api/settings/general")
    suspend fun getGeneralSettings(): Response<GeneralSettings>

    @PUT("api/settings/general")
    suspend fun updateGeneralSettings(@Body settings: UpdateGeneralSettingsRequest): Response<SettingsResponse>

    @GET("api/settings/platforms")
    suspend fun getPlatformSettings(): Response<PlatformSettingsResponse>

    @POST("api/settings/platforms")
    suspend fun updatePlatformSettings(@Body platforms: Map<String, @JvmSuppressWildcards Map<String, Any>>): Response<SettingsResponse>

    @GET("api/tier-limits")
    suspend fun getTierLimits(): Response<TierLimits>

    @POST("api/tier-limits")
    suspend fun updateTierLimits(@Body limits: TierLimits): Response<SettingsResponse>

    // ==================== المستخدمين ====================
    @GET("api/users")
    suspend fun getUsers(): Response<List<BotUser>>

    @GET("api/users/search")
    suspend fun searchUsers(@Query("q") query: String): Response<List<BotUser>>

    @GET("api/users/{id}")
    suspend fun getUser(@Path("id") userId: Int): Response<BotUser>

    @PUT("api/users/{id}")
    suspend fun updateUser(
        @Path("id") userId: Int,
        @Body updates: Map<String, @JvmSuppressWildcards Any>
    ): Response<GenericResponse>

    @POST("api/users/{id}/ban")
    suspend fun banUser(@Path("id") userId: Int): Response<GenericResponse>

    @POST("api/users/{id}/unban")
    suspend fun unbanUser(@Path("id") userId: Int): Response<GenericResponse>

    @GET("api/users/banned")
    suspend fun getBannedUsers(): Response<List<BotUser>>

    @GET("api/online-users")
    suspend fun getOnlineUsers(): Response<OnlineUsersResponse>

    // ==================== الإدارة ====================
    @GET("api/admin/info")
    suspend fun getAdminInfo(): Response<AdminInfoResponse>

    @POST("api/admin/change-password")
    suspend fun changePassword(@Body request: ChangePasswordRequest): Response<GenericResponse>

    @POST("api/admin/broadcast")
    suspend fun broadcastMessage(@Body request: BroadcastRequest): Response<GenericResponse>

    @POST("api/admin/send-message")
    suspend fun sendMessage(@Body request: SendMessageRequest): Response<GenericResponse>

    @POST("api/admin/restart-server")
    suspend fun restartServer(): Response<GenericResponse>

    @GET("api/admin/activity-log")
    suspend fun getActivityLog(): Response<List<kotlinx.serialization.json.JsonObject>>

    @GET("api/login-history")
    suspend fun getLoginHistory(): Response<kotlinx.serialization.json.JsonObject>

    @GET("api/logs")
    suspend fun getLogs(
        @Query("n") n: Int = 100,
        @Query("level") level: String = "all"
    ): Response<List<kotlinx.serialization.json.JsonObject>>

    @GET("api/admin/logs")
    suspend fun getAdminLogs(): Response<List<kotlinx.serialization.json.JsonObject>>

}
