package com.tiktokforbot.admin

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.rememberNavController
import com.tiktokforbot.admin.ui.navigation.AppNavGraph
import com.tiktokforbot.admin.ui.theme.TiktokForBotTheme
import com.tiktokforbot.admin.viewmodel.AuthViewModel
import com.tiktokforbot.admin.viewmodel.BotViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val app = application as? TiktokForBotApp
        if (app == null) {
            Log.e("MainActivity", "Application is not TiktokForBotApp")
            finish()
            return
        }

        setContent {
            val darkModePref by app.sessionManager.darkMode.collectAsState(initial = "system")
            val systemDark = isSystemInDarkTheme()
            val isDark = when (darkModePref) {
                "dark" -> true
                "light" -> false
                else -> systemDark
            }

            TiktokForBotTheme(darkTheme = isDark) {
                val navController = rememberNavController()
                val authViewModel: AuthViewModel = viewModel()
                val botViewModel: BotViewModel = viewModel()

                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    AppNavGraph(
                        navController = navController,
                        authViewModel = authViewModel,
                        botViewModel = botViewModel
                    )
                }
            }
        }
    }
}
