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
echo "للتشغيل، تأكد من وجود متغيرات البيئة في istxbot/.env:"
echo "  DEV_BOT_TOKEN=your_bot_token"
echo "  DEEPSEEK_API_KEY=sk-..."
echo "  ADMIN_CHAT_ID=your_chat_id"
echo ""
echo "ثم شغّل:"
echo "  bash run.sh"
