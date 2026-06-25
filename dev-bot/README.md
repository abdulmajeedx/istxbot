# بوت إدارة التطوير — Dev Bot

بوت تلجرام مساعد لإدارة مشروع TikTokForBot، يستخدم DeepSeek API.

## المميزات
- **تحكم مباشر في @istxbot** — تشغيل، إيقاف، إعادة تشغيل، سجلات
- **AI Assistant** — أسئلة تطويرية، مراجعة كود، اقتراحات
- **مراقبة المشروع** — Git status، إحصائيات، APK
- **تقرير يومي** تلقائي

## الأوامر
| الأمر | الوظيفة |
|-------|---------|
| `/status` | حالة المشروع |
| `/botstatus` | حالة @istxbot |
| `/botstart` / `/botstop` / `/botrestart` | تحكم في البوت |
| `/botlogs` | آخر السجلات |
| `/ask <سؤال>` | اسأل DeepSeek |
| `/review` | مراجعة آخر تغيير |
| `/build` | بناء تطبيق الأندرويد |
| `/broadcast` | رسالة جماعية |

## التشغيل

```bash
DEV_BOT_TOKEN=xxx DEEPSEEK_API_KEY=xxx ADMIN_CHAT_ID=xxx python main.py
```

## الخدمة

`dev-bot.service` (systemd)
