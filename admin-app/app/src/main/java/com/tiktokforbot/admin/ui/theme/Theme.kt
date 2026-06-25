package com.tiktokforbot.admin.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val LightColorScheme = lightColorScheme(
    primary = Blue500,
    onPrimary = Color.White,
    primaryContainer = Blue50,
    onPrimaryContainer = Blue700,
    secondary = Green500,
    onSecondary = Color.White,
    secondaryContainer = Green50,
    onSecondaryContainer = Green700,
    tertiary = Orange500,
    onTertiary = Color.White,
    tertiaryContainer = Orange50,
    onTertiaryContainer = Orange800,
    error = Red500,
    onError = Color.White,
    errorContainer = Red50,
    onErrorContainer = Red700,
    background = BackgroundLight,
    onBackground = Gray900,
    surface = SurfaceLight,
    onSurface = Gray900,
    onSurfaceVariant = Gray600,
    outline = Gray400,
    outlineVariant = Gray200,
    surfaceVariant = Gray100,
    inverseSurface = Gray800,
    inverseOnSurface = Gray50,
    inversePrimary = Blue200
)

private val DarkColorScheme = darkColorScheme(
    primary = Blue400,
    onPrimary = Blue900,
    primaryContainer = Blue800,
    onPrimaryContainer = Blue100,
    secondary = Green400,
    onSecondary = Green900,
    secondaryContainer = Green800,
    onSecondaryContainer = Green100,
    tertiary = Orange400,
    onTertiary = Orange900,
    tertiaryContainer = Orange800,
    onTertiaryContainer = Orange100,
    error = Red300,
    onError = Red900,
    errorContainer = Red800,
    onErrorContainer = Red100,
    background = DarkBackground,
    onBackground = DarkText,
    surface = DarkSurface,
    onSurface = DarkText,
    onSurfaceVariant = DarkTextSecondary,
    outline = Gray500,
    outlineVariant = Gray700,
    surfaceVariant = DarkCard,
    inverseSurface = Gray200,
    inverseOnSurface = Gray800,
    inversePrimary = Blue700
)

@Composable
fun TiktokForBotTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    val view = LocalView.current

    if (!view.isInEditMode) {
        SideEffect {
            val activity = view.context as? Activity ?: return@SideEffect
            val window = activity.window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
