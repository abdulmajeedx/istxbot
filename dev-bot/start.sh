#!/bin/bash
export DEV_BOT_TOKEN="8945224416:AAF-ZQXsjE--5RW7e7z3SNj0b5a8Je-snsc"
export DEEPSEEK_API_KEY="sk-5FrXUZIPhQXfDrAPtMdEpqDW1EwcWKwh2jTST2Lm5WWS5QqbM9CgGq9YAiHVI3GZ"
export DEEPSEEK_API_URL="https://opencode.ai/zen/v1/chat/completions"
export DEEPSEEK_MODEL="deepseek-v4-flash-free"
export ADMIN_CHAT_ID="7333480585"
cd /home/ngm/tiktokforbot/backend/dev-bot
exec python3 dev_bot.py
