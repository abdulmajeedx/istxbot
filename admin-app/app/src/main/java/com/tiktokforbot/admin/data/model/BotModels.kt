package com.tiktokforbot.admin.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/* ===== المصادقة (Authentication) ===== */
@Serializable
data class LoginRequest(
    val username: String,
    val password: String
)

@Serializable
data class Verify2faRequest(
    val code: String
)

@Serializable
data class LoginResponse(
    val success: Boolean,
    val message: String? = null,
    @SerialName("requires_2fa") val requires2fa: Boolean = false,
    @SerialName("expires_in") val expiresIn: Int? = null
)

@Serializable
data class Verify2faResponse(
    val success: Boolean,
    val message: String? = null
)

/* ===== حالة البوت (Bot Status) ===== */
@Serializable
data class BotStatusResponse(
    val status: String = "inactive",
    @SerialName("bot_running") val botRunning: Boolean = false,
    val active: String = "inactive",
    val enabled: String = "enabled",
    val pid: String = "0",
    val memory: String = "N/A",
    val cpu: String = "N/A",
    @SerialName("start_time") val startTime: String = "N/A"
)

/* ===== الإحصائيات (Statistics) ===== */
@Serializable
data class StatsResponse(
    @SerialName("total_users") val totalUsers: Int = 0,
    @SerialName("total_downloads") val totalDownloads: Int = 0,
    @SerialName("total_visitors") val totalVisitors: Int = 0,
    @SerialName("total_points") val totalPoints: Int = 0,
    @SerialName("today_downloads") val todayDownloads: Int = 0,
    @SerialName("platform_stats") val platformStats: PlatformStats = PlatformStats()
)

@Serializable
data class PlatformStats(
    val youtube: Int = 0,
    val instagram: Int = 0,
    val tiktok: Int = 0,
    val twitter: Int = 0,
    val facebook: Int = 0,
    val spotify: Int = 0,
    val soundcloud: Int = 0,
    val snapchat: Int = 0,
    @SerialName("google_drive") val googleDrive: Int = 0,
    val pinterest: Int = 0
)

/* ===== الإعدادات العامة (General Settings) ===== */
@Serializable
data class GeneralSettings(
    @SerialName("max_file_size") val maxFileSize: Int = 200,
    @SerialName("default_quality") val defaultQuality: String = "best",
    @SerialName("rate_limiting") val rateLimiting: RateLimiting = RateLimiting(),
    @SerialName("url_validation") val urlValidation: Boolean = true,
    @SerialName("ban_bots") val banBots: Boolean = true
)

@Serializable
data class RateLimiting(
    val enabled: Boolean = true,
    @SerialName("max_per_minute") val maxPerMinute: Int = 30
)

@Serializable
data class UpdateGeneralSettingsRequest(
    @SerialName("max_file_size") val maxFileSize: Int? = null,
    @SerialName("default_quality") val defaultQuality: String? = null,
    @SerialName("rate_limiting") val rateLimiting: RateLimiting? = null,
    @SerialName("url_validation") val urlValidation: Boolean? = null,
    @SerialName("ban_bots") val banBots: Boolean? = null
)

@Serializable
data class SettingsResponse(
    val success: Boolean = true,
    val message: String? = null,
    @SerialName("requires_restart") val requiresRestart: Boolean = false
)

/* ===== إعدادات المنصات (Platform Settings) ===== */
@Serializable
data class PlatformSetting(
    val enabled: Boolean = true,
    @SerialName("daily_limit") val dailyLimit: Int = 50
)

@Serializable
data class PlatformSettingsResponse(
    val youtube: PlatformSetting = PlatformSetting(dailyLimit = 100),
    val instagram: PlatformSetting = PlatformSetting(),
    val tiktok: PlatformSetting = PlatformSetting(),
    val twitter: PlatformSetting = PlatformSetting(),
    val facebook: PlatformSetting = PlatformSetting(),
    val spotify: PlatformSetting = PlatformSetting(dailyLimit = 30),
    val soundcloud: PlatformSetting = PlatformSetting(),
    val snapchat: PlatformSetting = PlatformSetting(),
    @SerialName("google_drive") val googleDrive: PlatformSetting = PlatformSetting(dailyLimit = 100),
    val pinterest: PlatformSetting = PlatformSetting()
)

/* ===== حدود المستويات (Tier Limits) ===== */
@Serializable
data class TierLimits(
    val free: TierLimit = TierLimit(),
    val premium: TierLimit = TierLimit(50),
    val vip: TierLimit = TierLimit(200)
)

@Serializable
data class TierLimit(
    @SerialName("daily_limit") val dailyLimit: Int = 10,
    val price: Double = 0.0
)

/* ===== المستخدمين (Users) ===== */
@Serializable
data class BotUser(
    @SerialName("user_id") val userId: Int = 0,
    val username: String? = null,
    @SerialName("first_name") val firstName: String? = null,
    val tier: String = "free",
    val points: Int = 0,
    val status: String = "active",
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("is_banned") val _isBannedRaw: kotlinx.serialization.json.JsonElement? = null,
    @SerialName("is_visitor") val _isVisitorRaw: kotlinx.serialization.json.JsonElement? = null,
    @SerialName("total_downloads") val totalDownloads: Int = 0
) {
    // محول آمن — API قد يرجع 0/1 أو true/false
    val isBanned: Boolean get() = when {
        _isBannedRaw == null -> false
        else -> _isBannedRaw.toString().trim('"') in listOf("1", "true")
    }
    val isVisitor: Boolean get() = when {
        _isVisitorRaw == null -> false
        else -> _isVisitorRaw.toString().trim('"') in listOf("1", "true")
    }
}

@Serializable
data class UsersResponse(
    val users: List<BotUser> = emptyList(),
    val total: Int = 0,
    val page: Int = 1
)

@Serializable
data class BanUserRequest(
    @SerialName("user_id") val userId: Int,
    val reason: String? = null
)

/* ===== الإدارة (Admin) ===== */
@Serializable
data class ChangePasswordRequest(
    @SerialName("current_password") val currentPassword: String,
    @SerialName("new_password") val newPassword: String
)

@Serializable
data class BroadcastRequest(
    val message: String,
    @SerialName("parse_mode") val parseMode: String = "HTML"
)

@Serializable
data class SendMessageRequest(
    @SerialName("user_id") val userId: Int,
    val message: String
)

@Serializable
data class AdminInfoResponse(
    val username: String = "admin",
    @SerialName("login_time") val loginTime: String? = null,
    @SerialName("login_ip") val loginIp: String? = null
)

/* ===== أناليتكس (Analytics) ===== */
@Serializable
data class AnalyticsResponse(
    @SerialName("total_users") val totalUsers: Int = 0,
    @SerialName("active_users_24h") val activeUsers24h: Int = 0,
    @SerialName("total_downloads") val totalDownloads: Int = 0,
    @SerialName("today_downloads") val todayDownloads: Int = 0,
    @SerialName("success_rate") val successRate: Double = 0.0,
    @SerialName("platform_stats") val platformStats: Map<String, Int> = emptyMap(),
    @SerialName("top_users") val topUsers: List<TopUser> = emptyList(),
    @SerialName("monthly_visitors") val monthlyVisitors: Int = 0
)

@Serializable
data class TopUser(
    @SerialName("user_id") val userId: Int,
    val downloads: Int
)

@Serializable
data class GenericResponse(
    val success: Boolean = true,
    val message: String? = null,
    val error: String? = null
)

/* ===== التحديث (App Update) ===== */
@Serializable
data class UpdateInfo(
    @SerialName("version_code") val versionCode: Int = 0,
    @SerialName("version_name") val versionName: String = "",
    @SerialName("download_url") val downloadUrl: String = "",
    val changelog: String = "",
    @SerialName("force_update") val forceUpdate: Boolean = false
)

/* ===== الأونلاين (Online Users) ===== */
@Serializable
data class OnlineUser(
    @SerialName("user_id") val userId: Int,
    val username: String? = null,
    val action: String? = null,
    @SerialName("last_active") val lastActive: String? = null
)

@Serializable
data class OnlineUsersResponse(
    val users: List<OnlineUser> = emptyList(),
    val count: Int = 0
)
