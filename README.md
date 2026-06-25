# TikTokForBot — منصة تحميل وسائط متعددة المنصات

> **المالك:** Abdulmajeed Alarmani | **الرخصة:** MIT

---

## 🗂️ هيكلة المشروع

```
tiktokforbot/
│
├── 📁 istxbot/              ← @istxbot - بوت التحميل (Telegram Bot)
│   ├── bot/                        كود البوت (Python/aiogram)
│   ├── web/                        منصة الويب (Python/Flask)
│   └── config/                     إعدادات
│
├── 📁 admin-app/            ← تطبيق إدارة البوت (Android/Kotlin)
│   └── com.tiktokforbot.admin/    Jetpack Compose + MVVM
│
├── 📁 utility-app/          ← تطبيق سناب المساعد (Android/Kotlin)
│   └── com.snapp.app/             Camera + Gallery
│
├── 📁 dev-bot/              ← بوت مساعد التطوير (Python + DeepSeek AI)
│
├── 📁 monitor/              ← لوحة مراقبة السيرفر (Python/Flask + psutil)
│
├── 📁 shared/               ← مكتبات مشتركة بين البوتات
│
├── 📁 plugins/              ← إضافات ووردبريس
│   ├── tiktokdl-panel/            لوحة تحكم TikTokDL
│   └── utility-app-panel/         لوحة تطبيق سناب
│
├── 📁 scripts/              ← سكربتات النشر والتشغيل
├── 📁 nginx/                ← إعدادات Nginx
└── 📁 docs/                 ← التوثيق
```

## 🚀 النشر

| الخدمة | Systemd | المنفذ |
|--------|---------|--------|
| @istxbot | `telegram-bot.service` | Polling |
| Web Control | `bot-web-control.service` | 8082 |
| Dev Bot | `dev-bot.service` | Polling |
| Monitor | `monitor.service` | 8090 |
| TikTok Web | `tiktok-web.service` | 8080 |

## 📦 المتطلبات

```bash
pip install aiogram yt-dlp Flask waitress aiosqlite cryptography requests python-dotenv
```

## 📝 ترخيص

MIT License © 2025 Abdulmajeed Alarmani
