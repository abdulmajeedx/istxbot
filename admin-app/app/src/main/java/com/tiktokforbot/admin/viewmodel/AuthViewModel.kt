package com.tiktokforbot.admin.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.tiktokforbot.admin.TiktokForBotApp
import com.tiktokforbot.admin.data.local.AppLogger
import com.tiktokforbot.admin.data.repository.BotRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AuthUiState(
    val isLoading: Boolean = false,
    val isCheckingSession: Boolean = true,
    val isLoggedIn: Boolean = false,
    val requires2fa: Boolean = false,
    val error: String? = null,
    val step: AuthStep = AuthStep.LOGIN,
    val debugTrace: String = ""
)

enum class AuthStep { LOGIN, VERIFY_2FA }

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = (application as? TiktokForBotApp)?.sessionManager
        ?: throw IllegalStateException("Application must be TiktokForBotApp")
    private val repository = BotRepository()
    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            try {
                kotlinx.coroutines.withTimeout(3000L) {
                    sessionManager.isLoggedIn.collect { loggedIn ->
                        _uiState.value = _uiState.value.copy(isCheckingSession = false, isLoggedIn = loggedIn)
                    }
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isCheckingSession = false)
            }
        }
    }

    fun login(username: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, debugTrace = "1.تسجيل الدخول...")
            try {
                repository.login(username, password)
                    .onSuccess { response ->
                        if (response.requires2fa) {
                            _uiState.value = _uiState.value.copy(
                                isLoading = false, requires2fa = true, step = AuthStep.VERIFY_2FA,
                                debugTrace = "2.تم إرسال رمز التحقق إلى تلجرام ✓"
                            )
                        } else if (response.success) {
                            _uiState.value = _uiState.value.copy(
                                isLoading = false, isLoggedIn = true, debugTrace = "2.تم الدخول ✓"
                            )
                            sessionManager.saveLoginState()
                        } else {
                            _uiState.value = _uiState.value.copy(
                                isLoading = false,
                                error = response.message ?: "فشل تسجيل الدخول",
                                debugTrace = "2.فشل: ${response.message}"
                            )
                        }
                    }
                    .onFailure { error ->
                        _uiState.value = _uiState.value.copy(
                            isLoading = false, error = error.toUserMessage(),
                            debugTrace = "2.خطأ: ${error.javaClass.simpleName}"
                        )
                    }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = "خطأ: ${e.message}")
            }
        }
    }

    fun verify2fa(code: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, debugTrace = "1.التحقق...")
            try {
                repository.verify2fa(code)
                    .onSuccess {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false, isLoggedIn = true, requires2fa = false,
                            debugTrace = "2.تم ✓"
                        )
                        sessionManager.saveLoginState()
                    }
                    .onFailure { error ->
                        _uiState.value = _uiState.value.copy(
                            isLoading = false, error = error.toUserMessage(),
                            debugTrace = "2.خطأ: ${error.javaClass.simpleName}"
                        )
                    }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = "خطأ: ${e.message}")
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            AppLogger.event("تسجيل الخروج")
            try { repository.logout() } catch (_: Exception) {}
            sessionManager.clearSession()
            _uiState.value = AuthUiState(isCheckingSession = false)
        }
    }

    fun clearError() { _uiState.value = _uiState.value.copy(error = null) }

    private fun Throwable.toUserMessage(): String = when (this) {
        is com.tiktokforbot.admin.data.api.ApiException -> message ?: "خطأ"
        is java.net.UnknownHostException -> "⚠️ تعذر الوصول إلى السيرفر"
        is javax.net.ssl.SSLException -> "⚠️ خطأ SSL"
        is java.net.SocketTimeoutException -> "⏱️ انتهت المهلة"
        is java.net.ConnectException -> "🔌 فشل الاتصال"
        is java.io.IOException -> "📡 خطأ شبكة: ${message}"
        else -> message ?: "خطأ غير معروف"
    }
}
