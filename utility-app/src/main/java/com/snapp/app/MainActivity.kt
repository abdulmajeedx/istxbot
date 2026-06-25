package com.snapp.app

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.snapp.app.ui.screens.CameraScreen
import com.snapp.app.ui.screens.HomeScreen
import com.snapp.app.ui.screens.PreviewScreen
import com.snapp.app.ui.theme.SnappTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            SnappApp()
        }
    }
}

sealed class SnappScreen {
    data object Home : SnappScreen()
    data object Camera : SnappScreen()
    data class Preview(val uri: Uri, val isVideo: Boolean) : SnappScreen()
}

@Composable
fun SnappApp() {
    SnappTheme {
        var currentScreen by remember { mutableStateOf<SnappScreen>(SnappScreen.Home) }

        when (val screen = currentScreen) {
            is SnappScreen.Home -> {
                HomeScreen(
                    onMediaReady = { uri, isVideo ->
                        currentScreen = SnappScreen.Preview(uri, isVideo)
                    },
                    onOpenCamera = {
                        currentScreen = SnappScreen.Camera
                    }
                )
            }
            is SnappScreen.Camera -> {
                CameraScreen(
                    onMediaCaptured = { uri, isVideo ->
                        currentScreen = SnappScreen.Preview(uri, isVideo)
                    },
                    onBack = {
                        currentScreen = SnappScreen.Home
                    }
                )
            }
            is SnappScreen.Preview -> {
                PreviewScreen(
                    mediaUri = screen.uri,
                    isVideo = screen.isVideo,
                    onRetake = {
                        currentScreen = SnappScreen.Camera
                    },
                    onBackToHome = {
                        currentScreen = SnappScreen.Home
                    }
                )
            }
        }
    }
}
