package com.tiktokforbot.admin.ui.screens

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import com.tiktokforbot.admin.viewmodel.BotViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    botViewModel: BotViewModel,
    onNavigateToSettings: () -> Unit,
    onNavigateToUsers: () -> Unit = {},
    onNavigateToLogs: () -> Unit = {},
    onLogout: () -> Unit
) {
    val uiState by botViewModel.uiState.collectAsState()
    var showRestartServerDialog by remember { mutableStateOf(false) }
    val lifecycleOwner = LocalLifecycleOwner.current

    // تحميل أولي + تحديث تلقائي مع احترام دورة حياة النشاط
    LaunchedEffect(lifecycleOwner) {
        // التحميل الأول
        botViewModel.loadDashboard()
        botViewModel.loadOnlineUsers()

        // تحديث دوري فقط عندما يكون التطبيق في المقدمة
        while (isActive) {
            delay(30_000)
            if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
                botViewModel.loadDashboard()
                botViewModel.loadOnlineUsers()
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("لوحة التحكم", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = onNavigateToLogs) {
                        Icon(Icons.AutoMirrored.Filled.Article, contentDescription = "السجلات")
                    }
                    IconButton(onClick = onNavigateToUsers) {
                        Icon(Icons.Default.People, contentDescription = "المستخدمين")
                    }
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "الإعدادات")
                    }
                    IconButton(onClick = { showRestartServerDialog = true }) {
                        Icon(Icons.Default.RestartAlt, contentDescription = "إعادة تشغيل السيرفر")
                    }
                    IconButton(onClick = onLogout) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = "تسجيل الخروج")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    actionIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        }
    ) { padding ->
        if (uiState.isLoading && uiState.botStatus == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // بطاقة حالة البوت
                item {
                    val status = uiState.botStatus
                    BotStatusCard(
                        botRunning = status?.botRunning ?: false,
                        statusText = status?.status ?: "inactive",
                        pid = status?.pid,
                        memory = status?.memory,
                        cpu = status?.cpu,
                        onStart = { botViewModel.startBot() },
                        onStop = { botViewModel.stopBot() },
                        onRestart = { botViewModel.restartBot() }
                    )
                }

                // معلومات الأدمن
                uiState.adminInfo?.let { admin ->
                    item {
                        Card(
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.AdminPanelSettings, null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(Modifier.width(12.dp))
                                Column {
                                    Text("@${admin.username}", style = MaterialTheme.typography.titleMedium,
                                        color = MaterialTheme.colorScheme.onSurface)
                                    admin.loginIp?.let {
                                        Text("IP: $it", style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }

                // بطاقات الإحصائيات
                item {
                    Text("الإحصائيات", style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onBackground)
                }

                item {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        StatCard(Modifier.weight(1f), Icons.Default.People, "المستخدمين",
                            formatNumber(uiState.stats.totalUsers), MaterialTheme.colorScheme.primary)
                        StatCard(Modifier.weight(1f), Icons.Default.Download, "التحميلات",
                            formatNumber(uiState.stats.totalDownloads), MaterialTheme.colorScheme.secondary)
                    }
                }

                item {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        StatCard(Modifier.weight(1f), Icons.Default.Today, "تحميلات اليوم",
                            formatNumber(uiState.stats.todayDownloads), MaterialTheme.colorScheme.tertiary)
                        StatCard(Modifier.weight(1f), Icons.Default.Visibility, "الزوار",
                            formatNumber(uiState.stats.totalVisitors), MaterialTheme.colorScheme.primary)
                    }
                }

                // إحصائيات المنصات
                item {
                    Text("المنصات", style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onBackground)
                }

                uiState.stats.platformStats.let { ps ->
                    val platformData = listOf(
                        "YouTube" to ps.youtube to Icons.Default.PlayCircle,
                        "TikTok" to ps.tiktok to Icons.Default.MusicNote,
                        "Instagram" to ps.instagram to Icons.Default.CameraAlt,
                        "Twitter" to ps.twitter to Icons.Default.Tag,
                        "Facebook" to ps.facebook to Icons.Default.Facebook,
                        "Spotify" to ps.spotify to Icons.Default.Headphones,
                        "SoundCloud" to ps.soundcloud to Icons.Default.Audiotrack,
                        "Snapchat" to ps.snapchat to Icons.Default.PhotoCamera,
                        "Google Drive" to ps.googleDrive to Icons.Default.Cloud,
                        "Pinterest" to ps.pinterest to Icons.Default.Bookmark
                    )

                    item {
                        Card(
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                            elevation = CardDefaults.cardElevation(2.dp)
                        ) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                platformData.forEach { (nameCount, icon) ->
                                    val (name, count) = nameCount
                                    if (count > 0) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Icon(icon, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                                            Spacer(Modifier.width(8.dp))
                                            Text(name, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium,
                                                color = MaterialTheme.colorScheme.onSurface)
                                            Text("$count", fontWeight = FontWeight.Bold,
                                                color = MaterialTheme.colorScheme.primary)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // الرسائل
                item {
                    uiState.error?.let { error ->
                        Card(colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer),
                            shape = RoundedCornerShape(12.dp)) {
                            Text(error, color = MaterialTheme.colorScheme.onErrorContainer,
                                modifier = Modifier.padding(16.dp))
                        }
                    }
                    uiState.successMessage?.let { msg ->
                        Card(colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.secondaryContainer),
                            shape = RoundedCornerShape(12.dp)) {
                            Text(msg, color = MaterialTheme.colorScheme.onSecondaryContainer,
                                modifier = Modifier.padding(16.dp))
                        }
                    }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    // حوار تأكيد إعادة تشغيل السيرفر
    if (showRestartServerDialog) {
        RestartServerDialog(
            onDismiss = { showRestartServerDialog = false },
            onConfirm = {
                showRestartServerDialog = false
                botViewModel.restartServer()
            }
        )
    }
}

@Composable
private fun BotStatusCard(
    botRunning: Boolean,
    statusText: String,
    pid: String?,
    memory: String?,
    cpu: String?,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onRestart: () -> Unit
) {
    val cardColor = if (botRunning) MaterialTheme.colorScheme.secondary
    else MaterialTheme.colorScheme.surfaceVariant
    val onCardColor = if (botRunning) MaterialTheme.colorScheme.onSecondary
    else MaterialTheme.colorScheme.onSurfaceVariant

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = cardColor)
    ) {
        Column(Modifier.fillMaxWidth().padding(20.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text("حالة البوت", style = MaterialTheme.typography.titleMedium, color = onCardColor)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = if (botRunning) "🟢 شغال" else "🔴 متوقف",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = onCardColor
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        pid?.let { if (it != "0") Text("PID: $it", style = MaterialTheme.typography.labelSmall, color = onCardColor.copy(alpha = 0.8f)) }
                        memory?.let { if (it != "N/A") Text("RAM: $it", style = MaterialTheme.typography.labelSmall, color = onCardColor.copy(alpha = 0.8f)) }
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (botRunning) {
                    FilledTonalButton(onClick = onStop, shape = CircleShape,
                        contentPadding = PaddingValues(12.dp),
                        colors = ButtonDefaults.filledTonalButtonColors(
                            containerColor = onCardColor.copy(alpha = 0.2f),
                            contentColor = onCardColor)) {
                        Icon(Icons.Default.Pause, "إيقاف", modifier = Modifier.size(20.dp))
                    }
                } else {
                    FilledTonalButton(onClick = onStart, shape = CircleShape,
                        contentPadding = PaddingValues(12.dp),
                        colors = ButtonDefaults.filledTonalButtonColors(
                            containerColor = onCardColor.copy(alpha = 0.2f),
                            contentColor = onCardColor)) {
                        Icon(Icons.Default.PlayArrow, "تشغيل", modifier = Modifier.size(20.dp))
                    }
                }
                FilledTonalButton(onClick = onRestart, shape = CircleShape,
                    contentPadding = PaddingValues(12.dp),
                    colors = ButtonDefaults.filledTonalButtonColors(
                        containerColor = onCardColor.copy(alpha = 0.2f),
                        contentColor = onCardColor)) {
                    Icon(Icons.Default.Refresh, "إعادة تشغيل", modifier = Modifier.size(20.dp))
                }
            }
        }
    }
}

@Composable
private fun StatCard(
    modifier: Modifier = Modifier,
    icon: ImageVector,
    label: String,
    value: String,
    color: Color
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(2.dp)
    ) {
        Column(Modifier.padding(16.dp)) {
            Surface(shape = RoundedCornerShape(12.dp), color = color.copy(alpha = 0.1f)) {
                Box(Modifier.padding(8.dp)) {
                    Icon(icon, null, tint = color, modifier = Modifier.size(24.dp))
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(value, style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
            Text(label, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun formatNumber(number: Int): String = when {
    number >= 1_000_000 -> "${number / 1_000_000}M"
    number >= 1_000 -> "${number / 1_000}K"
    else -> number.toString()
}

@Composable
private fun RestartServerDialog(
    onDismiss: () -> Unit,
    onConfirm: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Default.Warning, null, tint = MaterialTheme.colorScheme.tertiary) },
        title = { Text("إعادة تشغيل السيرفر") },
        text = {
            Text(
                "هل أنت متأكد من إعادة تشغيل السيرفر؟\n\n" +
                "سيؤدي ذلك إلى إعادة تشغيل خادم البوت بالكامل وقد يستغرق بضع ثوانٍ. " +
                "سيتم قطع اتصال جميع المستخدمين مؤقتاً."
            )
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.tertiary)
            ) {
                Icon(Icons.Default.RestartAlt, null, Modifier.size(16.dp))
                Spacer(Modifier.width(4.dp))
                Text("إعادة التشغيل")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("إلغاء") }
        }
    )
}
