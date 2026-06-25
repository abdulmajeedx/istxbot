#!/usr/bin/env python3
"""
🤖 بوت إدارة التطوير — TikTokForBot Dev Assistant
يستخدم DeepSeek API للإجابة عن أسئلة التطوير ومراقبة المشروع
"""

import os
import sys
import json
import subprocess
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ── الإعدادات ──────────────────────────────────────────
BOT_TOKEN = os.getenv("DEV_BOT_TOKEN", "")          # ضع Token بوت تلجرام هنا
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
PROJECT_DIR = Path("/home/ngm/tiktokforbot")
LOG_DIR = PROJECT_DIR / "backend/dev-bot/logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # Chat ID للمشرف
BOT_SERVICE = "telegram-bot"  # اسم خدمة systemd
BOT_DIR = Path("/home/ngm/bot_download_telegram")
BOT_DB = BOT_DIR / "bot_data.db"

# دوال مساعدة للصلاحيات
def is_admin(update: Update) -> bool:
    return str(update.effective_user.id) == str(ADMIN_CHAT_ID)

# ── التحكم المباشر في @tiktokforbot (systemctl + DB) ────
def run_cmd(cmd: list) -> tuple:
    """تشغيل أمر وإرجاع (نجاح, مخرجات)"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return False, str(e)

def get_bot_status() -> str:
    """حالة @tiktokforbot — مباشر من systemctl"""
    ok, out = run_cmd(["systemctl", "is-active", BOT_SERVICE])
    status = out
    ok2, pid = run_cmd(["systemctl", "show", BOT_SERVICE, "-p", "MainPID"])
    ok3, mem = run_cmd(["systemctl", "show", BOT_SERVICE, "-p", "MemoryCurrent"])
    ok4, cpu = run_cmd(["systemctl", "show", BOT_SERVICE, "-p", "CPUUsageNSec"])

    emoji = "🟢" if status == "active" else "🔴" if status == "inactive" else "🟡"
    return f"{emoji} {status}\nPID: {pid.split('=')[-1]}\nRAM: {mem.split('=')[-1]}"

def get_bot_stats() -> str:
    """إحصائيات @tiktokforbot — مباشر من SQLite"""
    try:
        import sqlite3
        conn = sqlite3.connect(str(BOT_DB))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM visitors")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM visitors WHERE last_visit > datetime('now','-1 day')")
        active = c.fetchone()[0]
        conn.close()
        return f"👥 الكل: {users} | 📅 نشط اليوم: {active}"
    except Exception as e:
        return f"❌ {e}"

def get_bot_logs(lines: int = 30) -> str:
    """آخر سجلات البوت"""
    ok, out = run_cmd(["journalctl", "-u", BOT_SERVICE, "--no-pager", "-n", str(lines)])
    return out[-1500:] if len(out) > 1500 else out

# ── DeepSeek AI ────────────────────────────────────────
def ask_deepseek(prompt: str, system_prompt: str = "") -> str:
    """استدعاء DeepSeek API"""
    if not DEEPSEEK_KEY:
        return "⚠️ لم يتم تعيين DEEPSEEK_API_KEY"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt or "أنت مساعد متخصص في تطوير تطبيق TikTokForBot. أجب بالعربية."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    try:
        r = requests.post(DEEPSEEK_URL, headers=headers, json=data, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return f"❌ API error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ فشل الاتصال: {e}"

# ── مراقبة المشروع ─────────────────────────────────────
def get_git_status() -> str:
    """حالة Git للمشروع"""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return "ليس مستودع Git"
        return result.stdout.strip() or "لا توجد تغييرات"
    except Exception as e:
        return f"خطأ في Git: {e}"

def get_git_log(count: int = 5) -> str:
    """آخر التغييرات"""
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--oneline", "--decorate"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or "لا يوجد تاريخ"
    except Exception:
        return "ليس مستودع Git"

def get_project_stats() -> str:
    """إحصائيات المشروع"""
    kt = len(list(PROJECT_DIR.rglob("*.kt")))
    py = len(list(PROJECT_DIR.rglob("*.py")))
    php = len(list(PROJECT_DIR.rglob("*.php")))
    return f"📁 Kotlin: {kt} | Python: {py} | PHP: {php}"

def get_apk_info() -> str:
    """معلومات آخر APK"""
    apk = PROJECT_DIR / "android/admin-app/app/build/outputs/apk/debug/app-debug.apk"
    if apk.exists():
        size_mb = apk.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(apk.stat().st_mtime)
        return f"📦 {size_mb:.1f} MB | 🕐 {mtime.strftime('%Y-%m-%d %H:%M')}"
    return "❌ لا يوجد APK"

# ── Telegram Bot Handlers ───────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start — للمشرف فقط"""
    if not is_admin(update):
        await update.message.reply_text("⛔ هذا البوت خاص بالمشرف فقط")
        return
    await update.message.reply_text(
        "🤖 **بوت إدارة تطوير TikTokForBot**\n\n"
        "أنا مساعدك في تطوير التطبيق. أستخدم DeepSeek AI للإجابة.\n\n"
        "📋 **أوامر المشروع:**\n"
        "/status — حالة المشروع\n"
        "/changes — آخر التغييرات\n"
        "/apk — معلومات الـ APK\n"
        "/build — بناء التطبيق\n"
        "/ask <سؤال> — اسأل DeepSeek\n"
        "/review — مراجعة آخر تغيير\n"
        "/suggest — اقتراحات تحسين\n"
        "\n"
        "🤖 **التحكم المباشر في @tiktokforbot:**\n"
        "/botstatus — حالة (systemctl)\n"
        "/botstart — تشغيل\n"
        "/botstop — إيقاف\n"
        "/botrestart — إعادة تشغيل\n"
        "/botlogs — آخر السجلات\n"
        "/broadcast — رسالة للمستخدمين",
        parse_mode="Markdown"
    )

def admin_only(func):
    """حماية الأوامر الحساسة — للمشرف فقط"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update):
            await update.message.reply_text("⛔ هذا الأمر للمشرف فقط")
            return
        return await func(update, context)
    return wrapper

@admin_only
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة المشروع"""
    msg = (
        f"📊 **حالة المشروع**\n\n"
        f"{get_project_stats()}\n"
        f"📝 Git: `{get_git_status()}`\n"
        f"📦 APK: {get_apk_info()}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

@admin_only
async def changes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آخر التغييرات"""
    log = get_git_log(5)
    await update.message.reply_text(f"📜 **آخر التغييرات:**\n\n{log}", parse_mode="Markdown")

@admin_only
async def apk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات الـ APK"""
    await update.message.reply_text(f"📦 {get_apk_info()}")

@admin_only
async def build_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بناء التطبيق"""
    await update.message.reply_text("🔨 جاري البناء...")
    try:
        result = subprocess.run(
            ["./gradlew", "assembleDebug"],
            cwd=PROJECT_DIR / "android/admin-app",
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            await update.message.reply_text(f"✅ **بناء ناجح!**\n{get_apk_info()}", parse_mode="Markdown")
        else:
            err = result.stderr[-500:] or result.stdout[-500:]
            await update.message.reply_text(f"❌ فشل البناء:\n```{err}```", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

@admin_only
async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اسأل DeepSeek"""
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text("استخدم: `/ask <سؤالك>`", parse_mode="Markdown")
        return
    await update.message.reply_text("🤔 جاري التفكير...")
    answer = ask_deepseek(
        question,
        system_prompt="أنت خبير في تطوير تطبيقات أندرويد (Kotlin/Jetpack Compose). المشروع اسمه TikTokForBot Admin — لوحة تحكم لبوت تلجرام. أجب بالعربية، كود نظيف، شرح واضح."
    )
    # تقسيم الرسائل الطويلة
    if len(answer) > 4000:
        for i in range(0, len(answer), 4000):
            await update.message.reply_text(answer[i:i+4000])
    else:
        await update.message.reply_text(answer)

@admin_only
async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مراجعة آخر تغيير"""
    log = get_git_log(1)
    if not log or "ليس" in log:
        await update.message.reply_text("لا يوجد Git لعرض التغييرات")
        return
    await update.message.reply_text("🔍 جاري مراجعة آخر تغيير...")
    review = ask_deepseek(
        f"راجع هذا التغيير في المشروع واقترح تحسينات:\n{log}",
        system_prompt="أنت مدقق كود. راجع التغيير واقترح تحسينات للأمان والأداء. أجب بالعربية في 3 نقاط."
    )
    await update.message.reply_text(f"📋 **مراجعة:**\n\n{review}")

# ── أوامر التحكم في @tiktokforbot ──────────────────────
@admin_only
async def botstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة البوت الرئيسي"""
    await update.message.reply_text(f"🤖 **@tiktokforbot**\n\n{get_bot_status()}\n📊 {get_bot_stats()}", parse_mode="Markdown")

@admin_only
async def botstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشغيل البوت"""
    ok, out = run_cmd(["sudo", "systemctl", "start", BOT_SERVICE])
    if ok:
        await update.message.reply_text("✅ تم تشغيل @tiktokforbot")
    else:
        await update.message.reply_text(f"❌ فشل:\n```{out[:500]}```", parse_mode="Markdown")

@admin_only
async def botstop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف البوت"""
    ok, out = run_cmd(["sudo", "systemctl", "stop", BOT_SERVICE])
    if ok:
        await update.message.reply_text("🛑 تم إيقاف @tiktokforbot")
    else:
        await update.message.reply_text(f"❌ فشل:\n```{out[:500]}```", parse_mode="Markdown")

@admin_only
async def botrestart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة تشغيل"""
    await update.message.reply_text("🔄 جاري إعادة تشغيل @tiktokforbot...")
    ok, out = run_cmd(["sudo", "systemctl", "restart", BOT_SERVICE])
    if ok:
        await update.message.reply_text(f"✅ تمت إعادة التشغيل\n{get_bot_status()}")
    else:
        await update.message.reply_text(f"❌ فشل:\n```{out[:500]}```", parse_mode="Markdown")

@admin_only
async def botlogs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آخر السجلات"""
    await update.message.reply_text(f"📜 **آخر السجلات:**\n```{get_bot_logs(20)}```", parse_mode="Markdown")

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة لكل مستخدمي البوت"""
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("استخدم: `/broadcast رسالتك هنا`", parse_mode="Markdown")
        return
    data = bot_api_call(f"/api/broadcast?message={requests.utils.quote(text)}", "POST")
    if data.get("success"):
        await update.message.reply_text(f"✅ تم الإرسال لـ {data.get('count',0)} مستخدم")
    else:
        await update.message.reply_text("❌ فشل الإرسال")

@admin_only
async def suggest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اقتراحات تحسين"""
    await update.message.reply_text("💡 جاري تحليل المشروع...")
    stats = get_project_stats()
    suggestion = ask_deepseek(
        f"اقترح 3 تحسينات لتطبيق أندرويد لإدارة بوت تلجرام. إحصائيات: {stats}. المشروع يستخدم Kotlin + Jetpack Compose + Retrofit. أجب بالعربية.",
        system_prompt="أنت مهندس برمجيات. اقترح تحسينات عملية وقابلة للتنفيذ. أجب بالعربية."
    )
    await update.message.reply_text(f"💡 **اقتراحات:**\n\n{suggestion}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على أي رسالة — للمشرف فقط"""
    if not is_admin(update):
        await update.message.reply_text("⛔ هذا البوت خاص بالمشرف فقط")
        return
    text = update.message.text
    if not text:
        return
    await update.message.reply_chat_action("typing")
    answer = ask_deepseek(text)
    if len(answer) > 4000:
        for i in range(0, len(answer), 4000):
            await update.message.reply_text(answer[i:i+4000])
    else:
        await update.message.reply_text(answer)

# ── الإشعارات التلقائية ─────────────────────────────────
async def send_daily_report(app: Application):
    """تقرير يومي تلقائي"""
    if not ADMIN_CHAT_ID:
        return
    msg = (
        f"📊 **التقرير اليومي — TikTokForBot**\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"{get_project_stats()}\n"
        f"📝 `{get_git_status()[:200]}`\n"
        f"📦 {get_apk_info()}"
    )
    try:
        await app.bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
    except Exception:
        pass

# ── Main ─────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ عيّن DEV_BOT_TOKEN في متغيرات البيئة")
        sys.exit(1)

    # تفعيل logging للتشخيص
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    app = Application.builder().token(BOT_TOKEN).build()

    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("changes", changes_cmd))
    app.add_handler(CommandHandler("apk", apk_cmd))
    app.add_handler(CommandHandler("build", build_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("review", review_cmd))
    app.add_handler(CommandHandler("suggest", suggest_cmd))
    app.add_handler(CommandHandler("botstatus", botstatus))
    app.add_handler(CommandHandler("botstart", botstart))
    app.add_handler(CommandHandler("botstop", botstop))
    app.add_handler(CommandHandler("botrestart", botrestart))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("botlogs", botlogs))

    # المحادثة العامة
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # معالج الأخطاء
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        print(f"❌ خطأ: {context.error}")
    app.add_error_handler(error_handler)

    # تقرير يومي (اختياري)
    try:
        app.job_queue.run_daily(send_daily_report, time=datetime.time(hour=9, minute=0))
    except Exception:
        pass  # JobQueue غير متوفر بدون pip install python-telegram-bot[job-queue]

    print("🤖 بوت إدارة التطوير يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
