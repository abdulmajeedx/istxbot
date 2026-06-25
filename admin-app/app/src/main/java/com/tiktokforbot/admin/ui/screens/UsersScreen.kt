package com.tiktokforbot.admin.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.tiktokforbot.admin.data.model.BotUser
import com.tiktokforbot.admin.viewmodel.BotViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UsersScreen(
    botViewModel: BotViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by botViewModel.uiState.collectAsState()
    var searchQuery by remember { mutableStateOf("") }
    var showBroadcastDialog by remember { mutableStateOf(false) }
    var showUserDetailDialog by remember { mutableStateOf<BotUser?>(null) }
    var showSendMessageDialog by remember { mutableStateOf<BotUser?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) { botViewModel.loadUsers() }

    LaunchedEffect(uiState.successMessage) {
        uiState.successMessage?.let { snackbarHostState.showSnackbar(it); botViewModel.clearMessages() }
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); botViewModel.clearMessages() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("المستخدمين", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "رجوع")
                    }
                },
                actions = {
                    IconButton(onClick = { showBroadcastDialog = true }) {
                        Icon(Icons.Default.Campaign, "بث رسالة")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    navigationIconContentColor = MaterialTheme.colorScheme.onPrimary,
                    actionIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            // شريط البحث
            OutlinedTextField(
                value = searchQuery,
                onValueChange = {
                    searchQuery = it
                    if (it.length >= 2) botViewModel.searchUsers(it)
                    else if (it.isEmpty()) botViewModel.loadUsers()
                },
                placeholder = { Text("ابحث عن مستخدم...") },
                leadingIcon = { Icon(Icons.Default.Search, null) },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = ""; botViewModel.loadUsers() }) {
                            Icon(Icons.Default.Close, null)
                        }
                    }
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                shape = RoundedCornerShape(12.dp)
            )

            if (uiState.isLoading && uiState.users.isEmpty()) {
                Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                }
            } else if (uiState.users.isEmpty()) {
                Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.PeopleOutline, null, Modifier.size(64.dp),
                            tint = MaterialTheme.colorScheme.outline)
                        Spacer(Modifier.height(16.dp))
                        Text("لا يوجد مستخدمين", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            } else {
                val listState = rememberLazyListState()
                val shouldLoadMore by remember {
                    derivedStateOf {
                        val lastVisibleItem = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
                        val totalItems = listState.layoutInfo.totalItemsCount
                        lastVisibleItem >= totalItems - 3 && !uiState.isLoadingMore && uiState.users.size < uiState.usersTotal
                    }
                }

                LaunchedEffect(shouldLoadMore) {
                    if (shouldLoadMore) botViewModel.loadMoreUsers()
                }

                LazyColumn(
                    state = listState,
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp)
                ) {
                    items(uiState.users, key = { it.userId }) { user ->
                        UserCard(
                            user = user,
                            onClick = { showUserDetailDialog = user },
                            onBan = { botViewModel.banUser(user.userId) },
                            onUnban = { botViewModel.unbanUser(user.userId) }
                        )
                    }
                    if (uiState.isLoadingMore) {
                        item {
                            Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(32.dp), strokeWidth = 3.dp)
                            }
                        }
                    }
                }
            }
        }

        // حوار البث الجماعي
        if (showBroadcastDialog) {
            BroadcastDialog(
                onDismiss = { showBroadcastDialog = false },
                onSend = { message ->
                    botViewModel.broadcastMessage(message)
                    showBroadcastDialog = false
                }
            )
        }

        // حوار تفاصيل المستخدم
        showUserDetailDialog?.let { user ->
            UserDetailDialog(
                user = user,
                onDismiss = { showUserDetailDialog = null },
                onBan = { botViewModel.banUser(user.userId); showUserDetailDialog = null },
                onUnban = { botViewModel.unbanUser(user.userId); showUserDetailDialog = null },
                onSendMessage = { showUserDetailDialog = null; showSendMessageDialog = user }
            )
        }

        // حوار إرسال رسالة لمستخدم
        showSendMessageDialog?.let { user ->
            SendMessageDialog(
                userName = user.firstName ?: user.username ?: "#${user.userId}",
                onDismiss = { showSendMessageDialog = null },
                onSend = { message ->
                    botViewModel.sendMessageToUser(user.userId, message)
                    showSendMessageDialog = null
                }
            )
        }
    }
}

@Composable
private fun UserCard(
    user: BotUser,
    onClick: () -> Unit,
    onBan: () -> Unit,
    onUnban: () -> Unit
) {
    Card(
        onClick = onClick,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(1.dp)
    ) {
        Row(
            Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // الصورة الرمزية
            val avatarBg = if (user.isBanned) MaterialTheme.colorScheme.errorContainer
            else MaterialTheme.colorScheme.primaryContainer
            val avatarText = if (user.isBanned) MaterialTheme.colorScheme.onErrorContainer
            else MaterialTheme.colorScheme.onPrimaryContainer

            Surface(
                shape = CircleShape,
                color = avatarBg,
                modifier = Modifier.size(44.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text(
                        (user.firstName?.first()?.uppercase() ?: user.username?.first()?.uppercase() ?: "?"),
                        fontWeight = FontWeight.Bold,
                        color = avatarText
                    )
                }
            }

            Spacer(Modifier.width(12.dp))

            Column(Modifier.weight(1f)) {
                Text(
                    text = user.firstName ?: user.username ?: "مستخدم #${user.userId}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("@${user.username ?: "—"}", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (user.isBanned) {
                        Surface(shape = RoundedCornerShape(4.dp),
                            color = MaterialTheme.colorScheme.errorContainer) {
                            Text("محظور", color = MaterialTheme.colorScheme.onErrorContainer,
                                style = MaterialTheme.typography.labelSmall,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                        }
                    }
                }
            }

            Column(horizontalAlignment = Alignment.End) {
                TierBadge(user.tier)
                Text("${user.totalDownloads}", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun TierBadge(tier: String) {
    val (color, label) = when (tier.lowercase()) {
        "premium" -> MaterialTheme.colorScheme.tertiary to "PRO"
        "vip" -> MaterialTheme.colorScheme.primary to "VIP"
        else -> MaterialTheme.colorScheme.outline to "مجاني"
    }
    Surface(shape = RoundedCornerShape(4.dp), color = color.copy(alpha = 0.1f)) {
        Text(label, color = color, style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
    }
}

@Composable
private fun UserDetailDialog(
    user: BotUser,
    onDismiss: () -> Unit,
    onBan: () -> Unit,
    onUnban: () -> Unit,
    onSendMessage: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(user.firstName ?: "مستخدم #${user.userId}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                DetailRow("المعرف", "${user.userId}")
                DetailRow("اليوزرنيم", "@${user.username ?: "—"}")
                DetailRow("المستوى", user.tier.uppercase())
                DetailRow("النقاط", "${user.points}")
                DetailRow("الحالة", if (user.isBanned) "محظور 🚫" else "نشط ✅")
                DetailRow("التحميلات", "${user.totalDownloads}")
                DetailRow("تاريخ الانضمام", user.createdAt ?: "—")
            }
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onSendMessage) {
                    Icon(Icons.AutoMirrored.Filled.Send, null, Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("رسالة")
                }
                if (user.isBanned) {
                    Button(onClick = onUnban,
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.secondary)) {
                        Text("إلغاء الحظر")
                    }
                } else {
                    Button(onClick = onBan,
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) {
                        Text("حظر")
                    }
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("إغلاق") }
        }
    )
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurface)
    }
}

@Composable
private fun BroadcastDialog(
    onDismiss: () -> Unit,
    onSend: (String) -> Unit
) {
    var message by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Default.Campaign, null, tint = MaterialTheme.colorScheme.primary) },
        title = { Text("إرسال بث للمستخدمين") },
        text = {
            OutlinedTextField(
                value = message,
                onValueChange = { message = it },
                placeholder = { Text("اكتب رسالتك هنا...") },
                supportingText = { Text("سيتم إرسال الرسالة لجميع مستخدمي البوت") },
                minLines = 4, maxLines = 8,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp)
            )
        },
        confirmButton = {
            Button(
                onClick = { onSend(message) },
                enabled = message.isNotBlank()
            ) { Text("إرسال البث") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("إلغاء") }
        }
    )
}

@Composable
private fun SendMessageDialog(
    userName: String,
    onDismiss: () -> Unit,
    onSend: (String) -> Unit
) {
    var message by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.AutoMirrored.Filled.Send, null, tint = MaterialTheme.colorScheme.primary) },
        title = { Text("إرسال رسالة إلى $userName") },
        text = {
            OutlinedTextField(
                value = message,
                onValueChange = { message = it },
                placeholder = { Text("اكتب رسالتك...") },
                minLines = 3, maxLines = 6,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp)
            )
        },
        confirmButton = {
            Button(
                onClick = { onSend(message) },
                enabled = message.isNotBlank()
            ) { Text("إرسال") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("إلغاء") }
        }
    )
}
