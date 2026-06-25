package com.tiktokforbot.admin.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tiktokforbot.admin.data.local.AppLogger
import com.tiktokforbot.admin.data.model.*
import com.tiktokforbot.admin.data.repository.BotRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class BotUiState(
    val isLoading: Boolean = false,
    val isLoadingMore: Boolean = false,
    val botStatus: BotStatusResponse? = null,
    val stats: StatsResponse = StatsResponse(),
    val analytics: AnalyticsResponse? = null,
    val generalSettings: GeneralSettings = GeneralSettings(),
    val platformSettings: PlatformSettingsResponse? = null,
    val tierLimits: TierLimits? = null,
    val users: List<BotUser> = emptyList(),
    val usersCurrentPage: Int = 1,
    val usersTotal: Int = 0,
    val onlineUsers: OnlineUsersResponse? = null,
    val adminInfo: AdminInfoResponse? = null,
    val logs: List<Map<String, String>> = emptyList(),
    val loginHistory: Map<String, String> = emptyMap(),
    val error: String? = null,
    val successMessage: String? = null
)

class BotViewModel : ViewModel() {

    private val repository = BotRepository()
    private val _uiState = MutableStateFlow(BotUiState())
    val uiState: StateFlow<BotUiState> = _uiState.asStateFlow()

    /** ترجمة أخطاء الاتصال إلى رسائل عربية */
    private fun Throwable.toUserMessage(): String {
        return when (this) {
            is com.tiktokforbot.admin.data.api.ApiException ->
                message ?: "خطأ في السيرفر"  // رسالة جاهزة لا نعيد تغليفها
            is java.net.UnknownHostException -> "⚠️ تعذر الوصول إلى السيرفر\nتأكد من اتصال الإنترنت"
            is javax.net.ssl.SSLException -> "⚠️ خطأ في شهادة الأمان SSL"
            is java.net.SocketTimeoutException -> "⏱️ انتهت مهلة الاتصال"
            is java.net.ConnectException -> "🔌 فشل الاتصال بالسيرفر"
            is java.io.IOException -> "📡 خطأ في الشبكة: ${message}"
            else -> message ?: "حدث خطأ غير معروف"
        }
    }

    fun loadDashboard() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            // استدعاءات متوازية لتسريع التحميل
            val statusDeferred = async { repository.getStatus() }
            val statsDeferred = async { repository.getStats() }
            val analyticsDeferred = async { repository.getAnalytics() }
            val adminInfoDeferred = async { repository.getAdminInfo() }

            val statusResult = statusDeferred.await()
            val statsResult = statsDeferred.await()
            val analyticsResult = analyticsDeferred.await()
            val adminInfoResult = adminInfoDeferred.await()

            // جمع الأخطاء من جميع النتائج
            val errors = listOfNotNull(
                statusResult.exceptionOrNull(),
                statsResult.exceptionOrNull(),
                analyticsResult.exceptionOrNull(),
                adminInfoResult.exceptionOrNull()
            )

            _uiState.value = _uiState.value.copy(
                isLoading = false,
                botStatus = statusResult.getOrNull(),
                stats = statsResult.getOrNull() ?: StatsResponse(),
                analytics = analyticsResult.getOrNull(),
                adminInfo = adminInfoResult.getOrNull(),
                error = errors.firstOrNull()?.toUserMessage()
            )
        }
    }

    fun loadSettings() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            val generalDeferred = async { repository.getGeneralSettings() }
            val platformsDeferred = async { repository.getPlatformSettings() }
            val tiersDeferred = async { repository.getTierLimits() }

            val generalResult = generalDeferred.await()
            val platformsResult = platformsDeferred.await()
            val tiersResult = tiersDeferred.await()

            val errors = listOfNotNull(
                generalResult.exceptionOrNull(),
                platformsResult.exceptionOrNull(),
                tiersResult.exceptionOrNull()
            )

            _uiState.value = _uiState.value.copy(
                isLoading = false,
                generalSettings = generalResult.getOrNull() ?: GeneralSettings(),
                platformSettings = platformsResult.getOrNull(),
                tierLimits = tiersResult.getOrNull(),
                error = errors.firstOrNull()?.toUserMessage()
            )
        }
    }

    fun loadUsers() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            repository.getUsers()
                .onSuccess { users ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        users = users,
                        usersTotal = users.size  // API يرجع كل المستخدمين دفعة واحدة
                    )
                }
                .onFailure { error ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = error.toUserMessage()
                    )
                }
        }
    }

    fun loadMoreUsers() {
        // API لا يدعم pagination — لا حاجة لتحميل المزيد
    }

    fun loadOnlineUsers() {
        viewModelScope.launch {
            repository.getOnlineUsers()
                .onSuccess { _uiState.value = _uiState.value.copy(onlineUsers = it) }
                .onFailure { /* silent fail */ }
        }
    }

    fun startBot() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            repository.startBot()
                .onSuccess { loadDashboard() }
                .onFailure { e -> _uiState.value = _uiState.value.copy(isLoading = false, error = e.toUserMessage()) }
        }
    }

    fun stopBot() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            repository.stopBot()
                .onSuccess { loadDashboard() }
                .onFailure { e -> _uiState.value = _uiState.value.copy(isLoading = false, error = e.toUserMessage()) }
        }
    }

    fun restartBot() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            repository.restartBot()
                .onSuccess { loadDashboard() }
                .onFailure { e -> _uiState.value = _uiState.value.copy(isLoading = false, error = e.toUserMessage()) }
        }
    }

    fun updateGeneralSettings(settings: UpdateGeneralSettingsRequest) {
        viewModelScope.launch {
            AppLogger.event("حفظ الإعدادات العامة")
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            repository.updateGeneralSettings(settings)
                .onSuccess { response ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = response.message ?: "تم حفظ الإعدادات"
                    )
                    loadSettings()
                }
                .onFailure { error ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = error.toUserMessage()
                    )
                }
        }
    }

    fun updatePlatformSettings(platform: String, enabled: Boolean, dailyLimit: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            val updates = mapOf(
                platform to mapOf(
                    "enabled" to enabled,
                    "daily_limit" to dailyLimit
                )
            )

            repository.updatePlatformSettings(updates)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "تم تحديث إعدادات المنصة"
                    )
                    loadSettings()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.toUserMessage()
                    )
                }
        }
    }

    fun updateTierLimits(limits: TierLimits) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            repository.updateTierLimits(limits)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "تم تحديث حدود المستويات"
                    )
                    loadSettings()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.toUserMessage()
                    )
                }
        }
    }

    fun banUser(userId: Int) {
        viewModelScope.launch {
            repository.banUser(userId)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(successMessage = "تم حظر المستخدم")
                    loadUsers()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(error = e.toUserMessage())
                }
        }
    }

    fun unbanUser(userId: Int) {
        viewModelScope.launch {
            repository.unbanUser(userId)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(successMessage = "تم إلغاء حظر المستخدم")
                    loadUsers()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(error = e.toUserMessage())
                }
        }
    }

    fun searchUsers(query: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                usersCurrentPage = 1,
                usersTotal = 0   // نتائج البحث لا تدعم التصفح
            )
            repository.searchUsers(query)
                .onSuccess { users -> _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    users = users,
                    usersTotal = users.size
                )}
                .onFailure { e -> _uiState.value = _uiState.value.copy(isLoading = false, error = e.toUserMessage()) }
        }
    }

    fun changePassword(currentPassword: String, newPassword: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            repository.changePassword(currentPassword, newPassword)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "تم تغيير كلمة المرور بنجاح"
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.toUserMessage()
                    )
                }
        }
    }

    fun broadcastMessage(message: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            repository.broadcastMessage(message)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(isLoading = false, successMessage = "تم إرسال البث لجميع المستخدمين")
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.toUserMessage())
                }
        }
    }

    fun sendMessageToUser(userId: Int, message: String) {
        viewModelScope.launch {
            repository.sendMessageToUser(userId, message)
                .onSuccess { _uiState.value = _uiState.value.copy(successMessage = "تم إرسال الرسالة") }
                .onFailure { e -> _uiState.value = _uiState.value.copy(error = e.toUserMessage()) }
        }
    }

    fun restartServer() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            repository.restartServer()
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        successMessage = "تم إعادة تشغيل السيرفر بنجاح"
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.toUserMessage()
                    )
                }
        }
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(error = null, successMessage = null)
    }

    fun loadLogs(count: Int = 100) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.getLogs(count)
                .onSuccess { _uiState.value = _uiState.value.copy(isLoading = false, logs = it) }
                .onFailure { e -> _uiState.value = _uiState.value.copy(isLoading = false, error = e.toUserMessage()) }
        }
    }

    fun loadLoginHistory() {
        viewModelScope.launch {
            repository.getLoginHistory()
                .onSuccess { _uiState.value = _uiState.value.copy(loginHistory = it) }
                .onFailure { /* silent */ }
        }
    }
}
