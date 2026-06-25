package com.tiktokforbot.admin.ui.navigation

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.tiktokforbot.admin.data.local.UpdateManager
import com.tiktokforbot.admin.data.model.UpdateInfo
import com.tiktokforbot.admin.data.repository.BotRepository
import com.tiktokforbot.admin.ui.components.UpdateAvailableDialog
import com.tiktokforbot.admin.ui.screens.*
import com.tiktokforbot.admin.viewmodel.AuthViewModel
import com.tiktokforbot.admin.viewmodel.BotViewModel
import kotlinx.coroutines.launch

object Routes {
    const val SPLASH = "splash"
    const val LOGIN = "login"
    const val DASHBOARD = "dashboard"
    const val SETTINGS = "settings"
    const val USERS = "users"
    const val LOGS = "logs"
}

@Composable
fun AppNavGraph(
    navController: NavHostController,
    authViewModel: AuthViewModel,
    botViewModel: BotViewModel
) {
    val uiState by authViewModel.uiState.collectAsState()

    NavHost(
        navController = navController,
        startDestination = Routes.SPLASH
    ) {
        // شاشة البداية - التحقق من الجلسة + فحص التحديثات
        composable(Routes.SPLASH) {
            val context = LocalContext.current
            val scope = rememberCoroutineScope()
            var updateInfo by remember { mutableStateOf<UpdateInfo?>(null) }
            var showUpdateDialog by remember { mutableStateOf(false) }

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.background),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = "🤖",
                        fontSize = 64.sp
                    )
                    Text(
                        text = "TikTokForBot",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(Modifier.height(24.dp))
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                }
            }

            // فحص التحديثات
            LaunchedEffect(Unit) {
                val repo = BotRepository()
                repo.checkUpdate()
                    .onSuccess { info ->
                        if (UpdateManager.hasUpdate(info)) {  // يشمل forceUpdate أيضاً
                            updateInfo = info
                            showUpdateDialog = true
                        }
                    }
                    .onFailure { /* فشل صامت */ }
            }

            // تسجيل/إلغاء مستقبل التنزيل
            DisposableEffect(Unit) {
                onDispose { /* cleanup */ }
            }

            // الانتقال بعد التحقق من الجلسة (فقط عندما لا يكون هناك حوار تحديث)
            LaunchedEffect(uiState.isCheckingSession, showUpdateDialog) {
                if (!uiState.isCheckingSession && !showUpdateDialog) {
                    val dest = if (uiState.isLoggedIn) Routes.DASHBOARD else Routes.LOGIN
                    navController.navigate(dest) {
                        popUpTo(Routes.SPLASH) { inclusive = true }
                    }
                }
            }

            // حوار التحديث
            if (showUpdateDialog && updateInfo != null) {
                UpdateAvailableDialog(
                    updateInfo = updateInfo!!,
                    onUpdateNow = {
                        // تنزيل في الخلفية ثم إغلاق الحوار (ينتقل LaunchedEffect)
                        val id = UpdateManager.downloadWithSystemManager(context, updateInfo!!)
                        UpdateManager.registerDownloadReceiver(context, id) { }
                        showUpdateDialog = false
                        // لا ننادي navController هنا — LaunchedEffect أعلاه يتولى الانتقال
                    },
                    onLater = {
                        showUpdateDialog = false
                    }
                )
            }
        }

        composable(Routes.LOGIN) {
            LoginScreen(
                authViewModel = authViewModel,
                onLoginSuccess = {
                    navController.navigate(Routes.DASHBOARD) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.DASHBOARD) {
            DashboardScreen(
                botViewModel = botViewModel,
                onNavigateToSettings = { navController.navigate(Routes.SETTINGS) },
                onNavigateToUsers = { navController.navigate(Routes.USERS) },
                onNavigateToLogs = { navController.navigate(Routes.LOGS) },
                onLogout = {
                    authViewModel.logout()
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.SETTINGS) {
            SettingsScreen(
                botViewModel = botViewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Routes.USERS) {
            UsersScreen(
                botViewModel = botViewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Routes.LOGS) {
            LogsScreen(
                botViewModel = botViewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}
