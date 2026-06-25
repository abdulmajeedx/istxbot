#!/bin/bash
# إعداد بوت إدارة التطوير
echo "🤖 إعداد بوت إدارة تطوير TikTokForBot"
echo "======================================"
echo ""

# تثبيت الاعتماديات
pip install -r requirements.txt

echo ""
echo "✅ اكتمل التثبيت"
echo ""
echo "للتشغيل، عيّن متغيرات البيئة:"
echo "  export DEV_BOT_TOKEN='your_telegram_bot_token'"
echo "  export DEEPSEEK_API_KEY='sk-...'"
echo "  export ADMIN_CHAT_ID='7333480585'"
echo ""
echo "ثم شغّل:"
echo "  python3 dev_bot.py"
