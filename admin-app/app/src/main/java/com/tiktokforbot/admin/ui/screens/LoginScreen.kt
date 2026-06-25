package com.tiktokforbot.admin.ui.screens

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tiktokforbot.admin.TiktokForBotApp
import com.tiktokforbot.admin.viewmodel.AuthStep
import com.tiktokforbot.admin.viewmodel.AuthViewModel

@Composable
fun LoginScreen(authViewModel: AuthViewModel, onLoginSuccess: () -> Unit) {
    val uiState by authViewModel.uiState.collectAsState()
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var verificationCode by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    val focusManager = LocalFocusManager.current
    val context = LocalContext.current
    val app = context.applicationContext as? TiktokForBotApp
    val lastCrash by (app?.sessionManager?.lastCrash ?: kotlinx.coroutines.flow.flowOf("")).collectAsState(initial = "")

    LaunchedEffect(uiState.isLoggedIn) { if (uiState.isLoggedIn) onLoginSuccess() }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Box(Modifier.size(96.dp).clip(RoundedCornerShape(24.dp)).background(MaterialTheme.colorScheme.primary), contentAlignment = Alignment.Center) {
                Text("🤖", fontSize = 40.sp)
            }
            Spacer(Modifier.height(24.dp))
            Text("TikTokForBot", style = MaterialTheme.typography.displayLarge, color = MaterialTheme.colorScheme.onBackground)
            Text("لوحة تحكم البوت", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(48.dp))

            // مؤشر الخطوة
            if (uiState.step == AuthStep.VERIFY_2FA) {
                StepIndicator(2, 2)
                Spacer(Modifier.height(16.dp))
            }

            // الخطوة 1: اسم المستخدم + كلمة المرور
            AnimatedVisibility(visible = uiState.step == AuthStep.LOGIN) {
                Column {
                    OutlinedTextField(value = username, onValueChange = { username = it },
                        label = { Text("اسم المستخدم") }, leadingIcon = { Icon(Icons.Default.Person, null) },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                        keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(androidx.compose.ui.focus.FocusDirection.Down) }),
                        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(value = password, onValueChange = { password = it },
                        label = { Text("كلمة المرور") }, leadingIcon = { Icon(Icons.Default.Lock, null) },
                        trailingIcon = { IconButton(onClick = { passwordVisible = !passwordVisible }) { Icon(if (passwordVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility, null) } },
                        visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); if (username.isNotBlank() && password.isNotBlank()) authViewModel.login(username, password) }),
                        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                }
            }

            // الخطوة 2: رمز التحقق
            AnimatedVisibility(visible = uiState.step == AuthStep.VERIFY_2FA) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("📱 تم إرسال رمز التحقق إلى تلجرام", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary, textAlign = TextAlign.Center)
                    Spacer(Modifier.height(16.dp))
                    OutlinedTextField(value = verificationCode, onValueChange = { if (it.length <= 6) verificationCode = it },
                        label = { Text("رمز التحقق") }, leadingIcon = { Icon(Icons.Default.Shield, null) },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); if (verificationCode.length >= 4) authViewModel.verify2fa(verificationCode) }),
                        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
                        supportingText = { Text("أدخل الرمز من تلجرام") })
                }
            }

            Spacer(Modifier.height(12.dp))

            // تتبع
            if (uiState.debugTrace.isNotEmpty()) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.5f)), shape = RoundedCornerShape(8.dp), modifier = Modifier.fillMaxWidth()) {
                    Text("🔍 ${uiState.debugTrace}", modifier = Modifier.padding(8.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSecondaryContainer)
                }
                Spacer(Modifier.height(8.dp))
            }

            // خطأ
            AnimatedVisibility(visible = uiState.error != null) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer), shape = RoundedCornerShape(8.dp)) {
                    Text(uiState.error ?: "", color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(12.dp), textAlign = TextAlign.Center)
                }
            }

            Spacer(Modifier.height(24.dp))

            // زر
            Button(onClick = {
                if (uiState.step == AuthStep.LOGIN) authViewModel.login(username, password)
                else authViewModel.verify2fa(verificationCode)
            }, enabled = when { uiState.isLoading -> false; uiState.step == AuthStep.LOGIN -> username.isNotBlank() && password.isNotBlank(); else -> verificationCode.length >= 4 },
                modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) {
                if (uiState.isLoading) CircularProgressIndicator(Modifier.size(24.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                else Text(if (uiState.step == AuthStep.LOGIN) "تسجيل الدخول" else "تأكيد", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }

            if (uiState.step == AuthStep.VERIFY_2FA) {
                Spacer(Modifier.height(12.dp))
                TextButton(onClick = { authViewModel.clearError(); authViewModel.login(username, password) }) {
                    Icon(Icons.Default.Refresh, null, Modifier.size(16.dp)); Spacer(Modifier.width(4.dp)); Text("إعادة إرسال الرمز")
                }
            }

            Spacer(Modifier.weight(1f))

            if (lastCrash.isNotEmpty()) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.7f)), shape = RoundedCornerShape(8.dp), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text("🚨 آخر كراش:", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onErrorContainer)
                        Text(lastCrash, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.8f))
                    }
                }
                Spacer(Modifier.height(8.dp))
            }

            if (uiState.step == AuthStep.LOGIN) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)), shape = RoundedCornerShape(8.dp)) {
                    Text("البيانات الافتراضية:\nاسم المستخدم: admin\nكلمة المرور: admin123", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(12.dp), textAlign = TextAlign.Center)
                }
                Spacer(Modifier.height(16.dp))
            }
        }
    }
}

@Composable
private fun StepIndicator(currentStep: Int, totalSteps: Int) {
    Row(horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
        for (i in 1..totalSteps) {
            Box(Modifier.size(if (i == currentStep) 32.dp else 28.dp).clip(RoundedCornerShape(50)).background(if (i == currentStep) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                Text("$i", color = if (i == currentStep) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            }
            if (i < totalSteps) Box(Modifier.width(48.dp).height(2.dp).background(if (i < currentStep) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant))
        }
    }
}
