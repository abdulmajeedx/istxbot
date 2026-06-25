# TikTokForBot Admin App

تطبيق أندرويد لإدارة بوت @istxbot عن بُعد.

## التقنيات
- **اللغة:** Kotlin
- **الواجهة:** Jetpack Compose + Material 3
- **المعمارية:** MVVM (ViewModel + Repository)
- **الشبكة:** Retrofit + kotlinx.serialization
- **التخزين المحلي:** Jetpack DataStore

## هيكل الحزمة

```
com.tiktokforbot.admin/
├── MainActivity.kt          النشاط الرئيسي
├── TiktokForBotApp.kt       تطبيق Application
├── data/
│   ├── api/                 Retrofit API service
│   ├── local/               SessionManager, AppLogger
│   ├── model/               BotModels (data classes)
│   └── repository/          BotRepository
├── service/                 NotificationHelper
├── ui/
│   ├── screens/             Dashboard, Login, Users, Settings, Logs
│   ├── navigation/          NavGraph
│   ├── components/          UpdateDialog
│   └── theme/               Color, Theme, Type
└── viewmodel/               AuthViewModel, BotViewModel
```

## الشاشات
1. **Splash** — شعار + تحقق من الجلسة + تحديثات
2. **تسجيل الدخول** — يوزر + باسورد + 2FA
3. **لوحة التحكم** — حالة البوت، إحصائيات، تحكم
4. **المستخدمين** — بحث، حظر، مراسلة
5. **الإعدادات** — تحكم كامل بإعدادات البوت
6. **السجلات** — سجلات السيرفر والمحلية

## البناء

```bash
./gradlew assembleDebug
```
