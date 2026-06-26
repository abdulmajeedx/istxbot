#!/bin/bash
# تشغيل بوت التطوير مع نموذج بديل — المتغيرات من ملف .env
set -a
source "$(dirname "$0")/../istxbot/.env" 2>/dev/null || true
set +a
export DEEPSEEK_API_URL="https://opencode.ai/zen/v1/chat/completions"
export DEEPSEEK_MODEL="deepseek-v4-flash-free"
cd "$(dirname "$0")"
exec python3 dev_bot.py
