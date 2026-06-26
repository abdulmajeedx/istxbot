#!/bin/bash
# تشغيل بوت التطوير — المتغيرات من ملف .env
set -a
source "$(dirname "$0")/../istxbot/.env" 2>/dev/null || true
set +a
cd "$(dirname "$0")"
exec python3 dev_bot.py
