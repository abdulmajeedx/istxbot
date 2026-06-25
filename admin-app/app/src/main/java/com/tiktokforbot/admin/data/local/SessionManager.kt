package com.tiktokforbot.admin.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withTimeout

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "session_prefs")

class SessionManager(private val context: Context) {

    companion object {
        private val KEY_IS_LOGGED_IN = booleanPreferencesKey("is_logged_in")
        private val KEY_LAST_LOGIN_TIME = longPreferencesKey("last_login_time")
        private val KEY_DARK_MODE = stringPreferencesKey("dark_mode")
    }

    val isLoggedIn: Flow<Boolean> = context.dataStore.data.map { preferences ->
        preferences[KEY_IS_LOGGED_IN] ?: false
    }

    private val KEY_ADMIN_TOKEN = stringPreferencesKey("admin_token")
    private val KEY_LAST_CRASH = stringPreferencesKey("last_crash")

    val darkMode: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[KEY_DARK_MODE] ?: "system"
    }

    val lastCrash: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[KEY_LAST_CRASH] ?: ""
    }

    suspend fun saveLoginState() {
        context.dataStore.edit { preferences ->
            preferences[KEY_IS_LOGGED_IN] = true
            preferences[KEY_LAST_LOGIN_TIME] = System.currentTimeMillis()
        }
    }

    suspend fun setDarkMode(mode: String) {
        context.dataStore.edit { preferences ->
            preferences[KEY_DARK_MODE] = mode
        }
    }

    /** حفظ توكن الأدمن بعد تسجيل الدخول */
    suspend fun saveAdminToken(token: String) {
        context.dataStore.edit { preferences ->
            preferences[KEY_ADMIN_TOKEN] = token
        }
    }

    /** تحميل التوكن المحفوظ — آمن لا يعلق أبداً */
    suspend fun getAdminToken(): String {
        return try {
            kotlinx.coroutines.withTimeout(2000L) {
                context.dataStore.data.first()[KEY_ADMIN_TOKEN] ?: ""
            }
        } catch (e: Exception) {
            ""
        }
    }

    suspend fun saveCrash(message: String) {
        context.dataStore.edit { preferences ->
            preferences[KEY_LAST_CRASH] = message
        }
    }

    suspend fun clearSession() {
        context.dataStore.edit { preferences ->
            preferences.clear()
        }
    }
}
