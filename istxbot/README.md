# @istxbot — بوت تحميل الفيديوهات

**Telegram:** [@istxbot](https://t.me/istxbot)  
**المالك:** Abdulmajeed Alarmani  
**المنصات:** 9 (TikTok, Instagram, YouTube, Twitter/X, Facebook, Snapchat, Pinterest, Spotify)

## الهيكل

```
istxbot/
├── bot/           ← كود البوت الأساسي (aiogram)
│   ├── main.py          نقطة التشغيل
│   ├── handlers/        معالجات الرسائل والأوامر
│   ├── downloaders/     محمّلات المنصات التسع
│   └── utils/           أدوات مساعدة (قاعدة بيانات، أمان، تشفير...)
├── web/           ← منصة الويب (Flask)
│   ├── app.py           تطبيق Flask
│   ├── templates/       قوالب HTML
│   └── static/          ملفات ثابتة
└── config/        ← إعدادات البوت
```

## النشر

- **السيرفر:** `/home/ngm/bot_download_telegram/`
- **الخدمة:** `telegram-bot.service` (systemd)
- **لوحة التحكم:** `bot-web-control.service` على المنفذ 8082

## التشغيل

```bash
cd bot/
python main.py
```
