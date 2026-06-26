#!/usr/bin/env python3
"""
منصة تحميل فيديوهات من مواقع التواصل عبر الويب
Multi-Platform Web Video Downloader with Activation Keys

الهيكلة الجديدة:
    app.py          ← نقطة الدخول الرئيسية (تسجيل blueprints وبدء التشغيل)
    common.py       ← الحالة والمساعدات المشتركة
    routes/
        public.py   ← الصفحات العامة و API العام
        admin.py    ← مسارات المشرف الأساسية (مصادقة، مفاتيح، إعدادات)
        admin_bot.py ← مسارات إدارة البوت (مستخدمين، webhook، شبح)
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

from flask import Flask, request, g

sys.path.insert(0, str(Path(__file__).parent.parent))


# استيراد الحالة والمسارات
from web.common import (
    db, BOT_TOKEN, ADMIN_PATH, APP_DIR, BASE_DIR, DB_PATH, DOWNLOAD_DIR,
    DEFAULT_PLATFORM, _email_otp,
    _detect_platform, _get_platform_config, _get_ads_settings,
    _ensure_db, _track_visitor, inject_site_settings,
    send_telegram_notification,
)
from web.routes.public import public_bp
from web.routes.admin import admin_bp
from web.routes.admin_bot import bot_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("web_app")

# ═══ إنشاء تطبيق Flask ═══

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# ═══ تسجيل Blueprints ═══

app.register_blueprint(public_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(bot_bp)


# ═══ Before/After Request Handlers ═══

@app.before_request
def _before_request():
    """ضمان تهيئة قاعدة البيانات وتتبع الزوار وكشف المنصة"""
    _ensure_db()
    _track_visitor()
    g.platform = _detect_platform()


@app.after_request
def _add_cache_headers(response):
    """إضافة رؤوس التخزين المؤقت المناسبة لكل نوع محتوى"""
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif response.content_type and ('css' in response.content_type or 'javascript' in response.content_type):
        response.headers['Cache-Control'] = 'public, max-age=300'
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@app.context_processor
def _inject_settings():
    """حقن إعدادات الموقع في جميع القوالب"""
    return inject_site_settings()


# ═══ تهيئة التطبيق ═══

_db_initialized = False


async def _init_db():
    await db.initialize()
    logger.info("Web app database initialized")


async def init_app():
    """تهيئة قاعدة البيانات والبوت (للمنادي الخارجي)"""
    global _db_initialized
    await _init_db()
    _db_initialized = True

    # تهيئة بوت تيليجرام عبر webhook
    from bot.webhook_setup import setup_bot, set_webhook
    if setup_bot():
        webhook_url = os.getenv("BOT_WEBHOOK_URL", "https://istx.io/api/bot/webhook")
        set_webhook(webhook_url)
    else:
        logger.error("Failed to initialize bot")


# ═══ نقطة التشغيل ═══

if __name__ == '__main__':
    import waitress

    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "8080"))

    asyncio.run(init_app())

    print("=" * 50)
    print("🌐 منصة تحميل الوسائط عبر الويب")
    print("=" * 50)
    print(f"🔗 الرابط: http://{host}:{port}")
    print(f"📊 قاعدة البيانات: {DB_PATH}")
    print(f"📥 مجلد التحميلات: {DOWNLOAD_DIR}")
    print("🛑 اضغط Ctrl+C للإيقاف")
    print()

    waitress.serve(app, host=host, port=port)


