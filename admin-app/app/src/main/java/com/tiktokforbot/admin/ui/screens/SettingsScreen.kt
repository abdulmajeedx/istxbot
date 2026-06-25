package com.tiktokforbot.admin.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.tiktokforbot.admin.TiktokForBotApp
import com.tiktokforbot.admin.data.local.UpdateManager
import com.tiktokforbot.admin.data.model.GeneralSettings
import com.tiktokforbot.admin.data.model.UpdateInfo
import com.tiktokforbot.admin.data.repository.BotRepository
import com.tiktokforbot.admin.ui.components.NoUpdateDialog
import com.tiktokforbot.admin.ui.components.UpdateAvailableDialog
import com.tiktokforbot.admin.ui.components.UpdateErrorDialog
import kotlinx.coroutines.launch
import com.tiktokforbot.admin.data.model.PlatformSettingsResponse
import com.tiktokforbot.admin.data.model.TierLimits
import com.tiktokforbot.admin.data.model.UpdateGeneralSettingsRequest
import com.tiktokforbot.admin.viewmodel.BotViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    botViewModel: BotViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by botViewModel.uiState.collectAsState()
    val settings = uiState.generalSettings

    var maxFileSize by remember(settings) { mutableStateOf(settings.maxFileSize.toString()) }
    var defaultQuality by remember(settings) { mutableStateOf(settings.defaultQuality) }
    var rateLimitEnabled by remember(settings) { mutableStateOf(settings.rateLimiting.enabled) }
    var maxPerMinute by remember(settings) { mutableStateOf(settings.rateLimiting.maxPerMinute.toString()) }
    var urlValidation by remember(settings) { mutableStateOf(settings.urlValidation) }
    var banBots by remember(settings) { mutableStateOf(settings.banBots) }

    val snackbarHostState = remember { SnackbarHostState() }
    var showChangePasswordDialog by remember { mutableStateOf(false) }

    // حالة التحديث
    var isCheckingUpdate by remember { mutableStateOf(false) }
    var updateInfo by remember { mutableStateOf<UpdateInfo?>(null) }
    var showUpdateDialog by remember { mutableStateOf(false) }
    var showNoUpdateDialog by remember { mutableStateOf(false) }
    var updateError by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val repository = remember { BotRepository() }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { botViewModel.loadSettings() }

    LaunchedEffect(uiState.successMessage) {
        uiState.successMessage?.let { snackbarHostState.showSnackbar(it); botViewModel.clearMessages() }
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); botViewModel.clearMessages() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("الإعدادات", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "رجوع")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    navigationIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        if (uiState.isLoading && uiState.generalSettings == GeneralSettings()) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                item { SectionHeader("إعدادات التحميل") }

                item {
                    OutlinedTextField(
                        value = maxFileSize,
                        onValueChange = { maxFileSize = it.filter { c -> c.isDigit() } },
                        label = { Text("الحد الأقصى لحجم الملف (MB)") },
                        leadingIcon = { Icon(Icons.Default.HourglassTop, null) },
                        supportingText = { Text("الحجم الحالي: ${settings.maxFileSize}MB") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp)
                    )
                }

                item {
                    var expanded by remember { mutableStateOf(false) }
                    val qualities = listOf("best" to "أفضل جودة", "medium" to "متوسط", "low" to "منخفض")

                    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
                        OutlinedTextField(
                            value = qualities.firstOrNull { it.first == defaultQuality }?.second ?: "أفضل جودة",
                            onValueChange = {}, readOnly = true,
                            label = { Text("الجودة الافتراضية") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                            leadingIcon = { Icon(Icons.Default.HighQuality, null) },
                            modifier = Modifier.fillMaxWidth()
                                .menuAnchor(MenuAnchorType.PrimaryNotEditable, enabled = true),
                            shape = RoundedCornerShape(12.dp)
                        )
                        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                            qualities.forEach { (code, name) ->
                                DropdownMenuItem(text = { Text(name) }, onClick = { defaultQuality = code; expanded = false })
                            }
                        }
                    }
                }

                item { SectionHeader("التحكم بالمعدل (Rate Limiting)") }

                item {
                    SettingsSwitch(
                        title = "تفعيل تحديد المعدل",
                        subtitle = "التحكم بعدد الطلبات في الدقيقة",
                        icon = Icons.Default.Speed, checked = rateLimitEnabled,
                        onCheckedChange = { rateLimitEnabled = it }
                    )
                }

                item {
                    OutlinedTextField(
                        value = maxPerMinute,
                        onValueChange = { maxPerMinute = it.filter { c -> c.isDigit() } },
                        label = { Text("الحد الأقصى للطلبات في الدقيقة") },
                        leadingIcon = { Icon(Icons.Default.Timer, null) },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
                        enabled = rateLimitEnabled
                    )
                }

                item { SectionHeader("الأمان") }

                item {
                    SettingsSwitch(
                        title = "التحقق من الروابط",
                        subtitle = "فحص صحة الروابط قبل التحميل",
                        icon = Icons.Default.VerifiedUser, checked = urlValidation,
                        onCheckedChange = { urlValidation = it }
                    )
                }

                item {
                    SettingsSwitch(
                        title = "حظر البوتات",
                        subtitle = "منع البوتات الآلية من استخدام الخدمة",
                        icon = Icons.Default.Block, checked = banBots,
                        onCheckedChange = { banBots = it }
                    )
                }

                // المظهر
                item { SectionHeader("المظهر") }

                item {
                    ThemeModeCard()
                }

                // إعدادات المنصات
                uiState.platformSettings?.let { ps ->
                    item { SectionHeader("المنصات") }

                    val platformList = listOf(
                        "youtube" to "YouTube" to Icons.Default.PlayCircle,
                        "tiktok" to "TikTok" to Icons.Default.MusicNote,
                        "instagram" to "Instagram" to Icons.Default.CameraAlt,
                        "twitter" to "Twitter/X" to Icons.Default.Tag,
                        "facebook" to "Facebook" to Icons.Default.Facebook,
                        "spotify" to "Spotify" to Icons.Default.Headphones,
                        "soundcloud" to "SoundCloud" to Icons.Default.Audiotrack,
                        "snapchat" to "Snapchat" to Icons.Default.PhotoCamera,
                        "google_drive" to "Google Drive" to Icons.Default.Cloud,
                        "pinterest" to "Pinterest" to Icons.Default.Bookmark
                    )

                    platformList.forEach { (keyName, icon) ->
                        val (key, name) = keyName
                        val setting = when (key) {
                            "youtube" -> ps.youtube
                            "tiktok" -> ps.tiktok
                            "instagram" -> ps.instagram
                            "twitter" -> ps.twitter
                            "facebook" -> ps.facebook
                            "spotify" -> ps.spotify
                            "soundcloud" -> ps.soundcloud
                            "snapchat" -> ps.snapchat
                            "google_drive" -> ps.googleDrive
                            "pinterest" -> ps.pinterest
                            else -> return@forEach
                        }
                        item {
                            PlatformCard(
                                name = name, icon = icon,
                                enabled = setting.enabled,
                                dailyLimit = setting.dailyLimit,
                                onToggle = { enabled ->
                                    botViewModel.updatePlatformSettings(key, enabled, setting.dailyLimit)
                                }
                            )
                        }
                    }
                }

                // حدود المستويات
                uiState.tierLimits?.let { tiers ->
                    item { SectionHeader("حدود المستويات (Tiers)") }

                    item { TierLimitCard("Free", tiers.free.dailyLimit, tiers.free.price, MaterialTheme.colorScheme.onSurfaceVariant) }
                    item { TierLimitCard("Premium", tiers.premium.dailyLimit, tiers.premium.price, MaterialTheme.colorScheme.tertiary) }
                    item { TierLimitCard("VIP", tiers.vip.dailyLimit, tiers.vip.price, MaterialTheme.colorScheme.primary) }
                }

                // فحص التحديثات
                item { SectionHeader("التحديث") }

                item {
                    UpdateCheckCard(
                        isChecking = isCheckingUpdate,
                        onCheckUpdate = {
                            isCheckingUpdate = true
                            updateError = null
                            scope.launch {
                                repository.checkUpdate()
                                    .onSuccess { info ->
                                        isCheckingUpdate = false
                                        if (UpdateManager.hasUpdate(info)) {
                                            updateInfo = info
                                            showUpdateDialog = true
                                        } else {
                                            showNoUpdateDialog = true
                                        }
                                    }
                                    .onFailure { e ->
                                        isCheckingUpdate = false
                                        updateError = e.message ?: "فشل التحقق"
                                    }
                            }
                        }
                    )
                }

                // تغيير كلمة المرور
                item { SectionHeader("كلمة المرور") }

                item {
                    ChangePasswordCard(onChangeClick = { showChangePasswordDialog = true })
                }

                // حفظ
                item {
                    Spacer(Modifier.height(8.dp))
                    Button(
                        onClick = {
                            botViewModel.updateGeneralSettings(
                                UpdateGeneralSettingsRequest(
                                    maxFileSize = maxFileSize.toIntOrNull(),
                                    defaultQuality = defaultQuality,
                                    rateLimiting = if (rateLimitEnabled)
                                        com.tiktokforbot.admin.data.model.RateLimiting(
                                            enabled = true,
                                            maxPerMinute = maxPerMinute.toIntOrNull() ?: 30
                                        ) else null,
                                    urlValidation = urlValidation,
                                    banBots = banBots
                                )
                            )
                        },
                        enabled = !uiState.isLoading,
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                    ) {
                        if (uiState.isLoading) {
                            CircularProgressIndicator(Modifier.size(24.dp),
                                color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Default.Save, null)
                            Spacer(Modifier.width(8.dp))
                            Text("حفظ الإعدادات", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        }
                    }
                    Spacer(Modifier.height(32.dp))
                }
            }
        }
    }

    // حوار تغيير كلمة المرور
    if (showChangePasswordDialog) {
        ChangePasswordDialog(
            isLoading = uiState.isLoading,
            onDismiss = { showChangePasswordDialog = false },
            onChangePassword = { currentPass, newPass ->
                botViewModel.changePassword(currentPass, newPass)
            }
        )
    }

    // حوارات التحديث
    if (showUpdateDialog && updateInfo != null) {
        UpdateAvailableDialog(
            updateInfo = updateInfo!!,
            onUpdateNow = {
                showUpdateDialog = false
                val id = UpdateManager.downloadWithSystemManager(context, updateInfo!!)
                UpdateManager.registerDownloadReceiver(context, id) {
                    // سيتم التثبيت تلقائياً بعد التنزيل
                }
            },
            onLater = {
                showUpdateDialog = false
            }
        )
    }

    if (showNoUpdateDialog) {
        NoUpdateDialog(onDismiss = { showNoUpdateDialog = false })
    }

    if (updateError != null) {
        UpdateErrorDialog(
            message = updateError!!,
            onDismiss = { updateError = null }
        )
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(title, style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.primary,
        fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
}

@Composable
private fun SettingsSwitch(
    title: String, subtitle: String, icon: ImageVector,
    checked: Boolean, onCheckedChange: (Boolean) -> Unit
) {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface)
                Text(subtitle, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(checked = checked, onCheckedChange = onCheckedChange,
                colors = SwitchDefaults.colors(
                    checkedThumbColor = MaterialTheme.colorScheme.onPrimary,
                    checkedTrackColor = MaterialTheme.colorScheme.primary))
        }
    }
}

@Composable
private fun PlatformCard(
    name: String, icon: ImageVector,
    enabled: Boolean, dailyLimit: Int,
    onToggle: (Boolean) -> Unit
) {
    val iconColor = if (enabled) MaterialTheme.colorScheme.primary
    else MaterialTheme.colorScheme.outline

    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = iconColor, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(name, style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface)
                Text("الحد اليومي: $dailyLimit تحميلة", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(checked = enabled, onCheckedChange = onToggle,
                colors = SwitchDefaults.colors(
                    checkedThumbColor = MaterialTheme.colorScheme.onPrimary,
                    checkedTrackColor = MaterialTheme.colorScheme.primary))
        }
    }
}

@Composable
private fun TierLimitCard(name: String, dailyLimit: Int, price: Double, color: Color) {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(shape = RoundedCornerShape(8.dp), color = color.copy(alpha = 0.1f)) {
                Box(Modifier.padding(8.dp)) {
                    Text(name.first().toString(), fontWeight = FontWeight.Bold, color = color)
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(name, style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface)
                Text("$dailyLimit تحميلة/يوم", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (price > 0) {
                Text("$${price.toInt()}", fontWeight = FontWeight.Bold, color = color)
            } else {
                Text("مجاني", color = MaterialTheme.colorScheme.outline,
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ThemeModeCard() {
    val context = LocalContext.current
    val app = context.applicationContext as? TiktokForBotApp ?: return
    val sessionManager = app.sessionManager
    val currentMode by sessionManager.darkMode.collectAsState(initial = "system")
    val coroutineScope = rememberCoroutineScope()

    var expanded by remember { mutableStateOf(false) }
    val modes = listOf(
        "system" to "حسب النظام",
        "light" to "فاتح",
        "dark" to "داكن"
    )
    val currentLabel = modes.firstOrNull { it.first == currentMode }?.second ?: "حسب النظام"
    val currentIcon = when (currentMode) {
        "dark" -> Icons.Default.DarkMode
        "light" -> Icons.Default.LightMode
        else -> Icons.Default.SettingsBrightness
    }

    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(currentIcon, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("وضع المظهر", style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface)
                Text(currentLabel, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            var dropExpanded by remember { mutableStateOf(false) }
            Box {
                IconButton(onClick = { dropExpanded = true }) {
                    Icon(Icons.Default.ArrowDropDown, null, tint = MaterialTheme.colorScheme.onSurface)
                }
                DropdownMenu(expanded = dropExpanded, onDismissRequest = { dropExpanded = false }) {
                    modes.forEach { (mode, label) ->
                        DropdownMenuItem(
                            text = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    val icon = when (mode) {
                                        "dark" -> Icons.Default.DarkMode
                                        "light" -> Icons.Default.LightMode
                                        else -> Icons.Default.SettingsBrightness
                                    }
                                    Icon(icon, null, Modifier.size(18.dp))
                                    Spacer(Modifier.width(8.dp))
                                    Text(label)
                                }
                            },
                            onClick = {
                                coroutineScope.launch { sessionManager.setDarkMode(mode) }
                                dropExpanded = false
                            },
                            leadingIcon = if (mode == currentMode) {
                                { Icon(Icons.Default.Check, null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.primary) }
                            } else null
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun UpdateCheckCard(
    isChecking: Boolean,
    onCheckUpdate: () -> Unit
) {
    Card(
        onClick = onCheckUpdate,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (isChecking) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = MaterialTheme.colorScheme.primary,
                    strokeWidth = 2.dp
                )
            } else {
                Icon(Icons.Default.SystemUpdate, null,
                    tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    if (isChecking) "جارٍ التحقق..." else "التحقق من وجود تحديثات",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    "ابحث عن نسخة جديدة من التطبيق",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Icon(Icons.Default.ChevronRight, null, tint = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
private fun ChangePasswordCard(onChangeClick: () -> Unit) {
    Card(
        onClick = onChangeClick,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Lock, null, tint = MaterialTheme.colorScheme.tertiary, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("تغيير كلمة المرور", style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface)
                Text("انقر لتغيير كلمة مرور الأدمن", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.Default.ChevronRight, null, tint = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
private fun ChangePasswordDialog(
    isLoading: Boolean,
    onDismiss: () -> Unit,
    onChangePassword: (String, String) -> Unit
) {
    var currentPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var currentVisible by remember { mutableStateOf(false) }
    var newVisible by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Default.Lock, null, tint = MaterialTheme.colorScheme.tertiary) },
        title = { Text("تغيير كلمة المرور") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = currentPassword,
                    onValueChange = { currentPassword = it; error = null },
                    label = { Text("كلمة المرور الحالية") },
                    leadingIcon = { Icon(Icons.Default.VpnKey, null) },
                    trailingIcon = {
                        IconButton(onClick = { currentVisible = !currentVisible }) {
                            Icon(
                                if (currentVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                null
                            )
                        }
                    },
                    visualTransformation = if (currentVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                )

                OutlinedTextField(
                    value = newPassword,
                    onValueChange = { newPassword = it; error = null },
                    label = { Text("كلمة المرور الجديدة") },
                    leadingIcon = { Icon(Icons.Default.LockReset, null) },
                    trailingIcon = {
                        IconButton(onClick = { newVisible = !newVisible }) {
                            Icon(
                                if (newVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                null
                            )
                        }
                    },
                    visualTransformation = if (newVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                )

                OutlinedTextField(
                    value = confirmPassword,
                    onValueChange = { confirmPassword = it; error = null },
                    label = { Text("تأكيد كلمة المرور الجديدة") },
                    leadingIcon = { Icon(Icons.Default.Shield, null) },
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    isError = error != null,
                    supportingText = error?.let { { Text(it, color = MaterialTheme.colorScheme.error) } }
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    when {
                        currentPassword.isBlank() -> error = "أدخل كلمة المرور الحالية"
                        newPassword.length < 4 -> error = "كلمة المرور الجديدة قصيرة جداً (الأقل 4 أحرف)"
                        newPassword != confirmPassword -> error = "كلمتا المرور غير متطابقتين"
                        else -> {
                            error = null
                            onChangePassword(currentPassword, newPassword)
                            onDismiss()
                        }
                    }
                },
                enabled = !isLoading,
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.tertiary)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(Modifier.size(16.dp),
                        color = MaterialTheme.colorScheme.onTertiary, strokeWidth = 2.dp)
                } else {
                    Text("تغيير")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("إلغاء") }
        }
    )
}
