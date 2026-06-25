#!/usr/bin/env python3
"""
منصة تحميل فيديوهات من مواقع التواصل عبر الويب
Multi-Platform Web Video Downloader with Activation Keys
"""

import os
import sys
import asyncio
import logging
import requests as http_requests
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, after_this_request, g

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.downloaders.tiktok_downloader import TikTokDownloader
from bot.utils.database import DatabaseManager, init_database
from config.settings import settings
from bot.webhook_setup import setup_bot, process_update, set_webhook, get_bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("web_app")

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(APP_DIR)

DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "bot_data.db"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", os.path.join(BASE_DIR, "downloads"))).resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

db = DatabaseManager(DB_PATH)
MAX_DAILY_DOWNLOADS_PER_KEY = 100
_db_initialized = False

# ── Platform-specific configs ──────────────────────────────────────────

_PLATFORM_CONFIGS = {
    "TikTok": {
        "site_title": "TikTok Downloader",
        "site_subtitle": "حمل فيديوهات TikTok بدون علامة مائية",
        "logo_svg": '<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M16.6 5.82s.51.5 0 0A4.28 4.28 0 0019.5 3h-3a1.5 1.5 0 00-1.5 1.5V12a3 3 0 11-2.12-2.87V6.1a6.5 6.5 0 106.58 5.9V5.82z" fill="#fe2c55"/><path d="M16.6 5.82s.51.5 0 0A4.28 4.28 0 0019.5 3h-3a1.5 1.5 0 00-1.5 1.5V12a3 3 0 11-2.12-2.87V6.1a6.5 6.5 0 106.58 5.9V5.82z" fill="#25f4ee" opacity="0.3"/></svg>',
        "accent_color": "#fe2c55",
        "cyan_color": "#25f4ee",
        "footer_text": "TikTok Downloader",
        "url_placeholder": "https://www.tiktok.com/@user/video/...",
        "url_pattern": "tiktok.com",
        "usage_text": "أدخل رابط TikTok ومفتاح التفعيل للتحميل",
        "domain": "tiktok",
        "download_btn_text": "تحميل",
    },
}

_DEFAULT_SITE_SETTINGS = {
    "logo_url": "",
    "logo_type": "svg",
    "banner_icon_url": "",
    "bg_color": "#0f0f0f",
    "card_color": "#1a1a2e",
    "contact_phone": os.getenv("SUPPORT_PHONE", "966XXXXXXXXX"),
    "contact_telegram": "qazvvx",
    "contact_whatsapp_label": "واتساب",
    "contact_telegram_label": "تيليجرام",
    "contact_whatsapp_icon": "",
    "contact_telegram_icon": "",
}

# ── Platform downloader instances ──────────────────────────────────────

_downloaders = {
    "TikTok": TikTokDownloader(),
}
for d in _downloaders.values():
    d.download_dir = DOWNLOAD_DIR

# ── Subdomain → platform mapping ───────────────────────────────────────
_SUBDOMAIN_MAP = {
    "tiktok": "TikTok",
}

DEFAULT_PLATFORM = "TikTok"


def _detect_platform() -> str:
    """Detect platform from Host header (subdomain)"""
    host = request.host.lower() if request else ""
    if not host:
        return DEFAULT_PLATFORM
    host_no_port = host.split(":")[0]
    parts = host_no_port.split(".")
    if len(parts) >= 3:
        sub = parts[0]
        if sub in _SUBDOMAIN_MAP:
            return _SUBDOMAIN_MAP[sub]
    if "istx.io" in host_no_port and host_no_port.count(".") >= 2:
        sub = host_no_port.split(".")[0]
        if sub in _SUBDOMAIN_MAP:
            return _SUBDOMAIN_MAP[sub]
    return DEFAULT_PLATFORM


def _get_platform_config() -> dict:
    """Get platform config merged with DB overrides (both global and platform-specific)"""
    platform = g.get("platform", DEFAULT_PLATFORM)
    default_config = _PLATFORM_CONFIGS.get(platform, _PLATFORM_CONFIGS[DEFAULT_PLATFORM])
    config = {**_DEFAULT_SITE_SETTINGS, **default_config}
    try:
        all_settings = asyncio.run(db.get_all_site_settings())
    except Exception:
        all_settings = {}
    # Apply global overrides (keys without prefix, skip empty values)
    for k, v in all_settings.items():
        if v and not k.startswith('TikTok:'):
            config[k] = v
    # Apply platform-specific overrides (prefixed keys, skip empty values)
    platform_prefix = f"{platform}:"
    for k, v in all_settings.items():
        if v and k.startswith(platform_prefix):
            config[k[len(platform_prefix):]] = v
    return config


def _get_downloader(platform: str = None):
    """Get the right downloader for a platform"""
    if platform is None:
        platform = g.get("platform", DEFAULT_PLATFORM)
    return _downloaders.get(platform, _downloaders[DEFAULT_PLATFORM])


@app.after_request
def _add_cache_headers(response):
    """Add proper cache headers for all responses"""
    # HTML pages: no cache
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    # Static assets: short cache
    elif response.content_type and ('css' in response.content_type or 'javascript' in response.content_type):
        response.headers['Cache-Control'] = 'public, max-age=300'
    # API responses: no cache
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@app.before_request
def _before_request():
    _ensure_db()
    _track_visitor()
    g.platform = _detect_platform()


def _get_ads_settings() -> dict:
    """Get ads settings from database. Returns empty string for disabled ads."""
    try:
        all_settings = asyncio.run(db.get_all_site_settings())
        ads = {}
        slots = ["top", "native", "middle", "after_steps", "bottom", "sticky_bottom"]
        for slot in slots:
            html = all_settings.get(f"ads:{slot}_html", "")
            enabled = all_settings.get(f"ads:{slot}_enabled", "true")
            # Store both; template uses truthy check on html, but we also expose enabled
            ads[f"{slot}_html"] = html if str(enabled).lower() in ("true", "1", "yes", "on") else ""
            ads[f"{slot}_enabled"] = str(enabled).lower() in ("true", "1", "yes", "on")
        return ads
    except Exception:
        return {}


@app.context_processor
def inject_site_settings():
    return {
        "site_settings": _get_platform_config(),
        "platform": g.get("platform", DEFAULT_PLATFORM),
        "ads_settings": _get_ads_settings()
    }


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")


def send_telegram_notification(text: str):
    """Send a Telegram message to the admin"""
    if not BOT_TOKEN or not ADMIN_ID:
        logger.warning("Cannot send notification: BOT_TOKEN or ADMIN_ID not set")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = http_requests.post(url, json={
            "chat_id": int(ADMIN_ID),
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code == 200:
            logger.info("Admin notification sent")
        else:
            logger.error(f"Notification failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")


# Email OTP store for key recovery
_email_otp = {}


def send_email_otp(email: str, otp: str) -> bool:
    """Send OTP code via email using SMTP"""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured for email OTP")
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = email
        msg['Subject'] = 'رمز استرجاع المفتاح - istx.io'

        body = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:400px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:#fe2c55">🔐 استرجاع المفتاح</h2>
<p style="color:#888">رمز التحقق الخاص بك هو:</p>
<div style="font-size:32px;font-weight:800;color:#fff;letter-spacing:8px;margin:16px 0">{otp}</div>
<p style="color:#666;font-size:12px">ينتهي الرمز بعد 5 دقائق</p>
<p style="color:#555;font-size:11px;margin-top:24px">إذا لم تطلب هذا الرمز، تجاهل هذه الرسالة</p>
</div></body></html>"""

        msg.attach(MIMEText(body, 'html', 'utf-8'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()

        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email OTP sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email OTP: {e}")
        return False


def send_subscription_email(email: str, subject: str, body_html: str) -> bool:
    """Send a subscription-related email to the user"""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured")
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()

        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logger.info(f"Subscription email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send subscription email: {e}")
        return False
    """Send OTP code via email using SMTP"""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured for email OTP")
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = email
        msg['Subject'] = 'رمز استرجاع المفتاح - istx.io'

        body = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:400px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:#fe2c55">🔐 استرجاع المفتاح</h2>
<p style="color:#888">رمز التحقق الخاص بك هو:</p>
<div style="font-size:32px;font-weight:800;color:#fff;letter-spacing:8px;margin:16px 0">{otp}</div>
<p style="color:#666;font-size:12px">ينتهي الرمز بعد 5 دقائق</p>
<p style="color:#555;font-size:11px;margin-top:24px">إذا لم تطلب هذا الرمز، تجاهل هذه الرسالة</p>
</div></body></html>"""

        msg.attach(MIMEText(body, 'html', 'utf-8'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()

        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email OTP sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email OTP: {e}")
        return False


def _ensure_db():
    """Ensure database is initialized (called before first request)"""
    global _db_initialized
    if not _db_initialized:
        asyncio.run(_init_db())
        _db_initialized = True


async def _init_db():
    await db.initialize()
    logger.info("Web app database initialized")


async def init_app():
    """Initialize database connection and bot (for external caller)"""
    await _init_db()
    if setup_bot():
        webhook_url = os.getenv("BOT_WEBHOOK_URL", "https://istx.io/api/bot/webhook")
        set_webhook(webhook_url)
    else:
        logger.error("Failed to initialize bot")


@app.before_request
def _before_request():
    """Ensure database tables exist before handling any request"""
    _ensure_db()
    _track_visitor()


def _track_visitor():
    """Record visitor information for analytics"""
    try:
        if request.path.startswith('/static') or request.path.startswith('/api'):
            return

        ip = (
            request.headers.get('CF-Connecting-IP') or
            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            request.remote_addr or 'unknown'
        )
        ua = request.headers.get('User-Agent', '')
        ua_lower = ua.lower()

        # Device type
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            device_type = 'mobile'
        elif 'tablet' in ua_lower or 'ipad' in ua_lower:
            device_type = 'tablet'
        else:
            device_type = 'desktop'

        # Browser
        if 'firefox' in ua_lower:
            browser = 'Firefox'
        elif 'edg' in ua_lower:
            browser = 'Edge'
        elif 'chrome' in ua_lower:
            browser = 'Chrome'
        elif 'safari' in ua_lower:
            browser = 'Safari'
        elif 'opera' in ua_lower:
            browser = 'Opera'
        else:
            browser = ua.split('/')[0][:30] if '/' in ua else 'Other'

        # OS
        if 'windows' in ua_lower:
            os_name = 'Windows'
        elif 'mac os' in ua_lower or 'macintosh' in ua_lower:
            os_name = 'macOS'
        elif 'android' in ua_lower:
            os_name = 'Android'
        elif 'linux' in ua_lower:
            os_name = 'Linux'
        elif 'iphone' in ua_lower or 'ipad' in ua_lower or 'ios' in ua_lower:
            os_name = 'iOS'
        else:
            os_name = 'Other'

        # Country from Cloudflare
        country = request.headers.get('CF-IPCountry', 'unknown')
        country_code = country if country != 'unknown' else '??'

        # Country name lookup
        COUNTRY_NAMES = {
            'SA': 'السعودية', 'AE': 'الإمارات', 'KW': 'الكويت', 'QA': 'قطر',
            'BH': 'البحرين', 'OM': 'عمان', 'EG': 'مصر', 'JO': 'الأردن',
            'IQ': 'العراق', 'SY': 'سوريا', 'LB': 'لبنان', 'PS': 'فلسطين',
            'YE': 'اليمن', 'LY': 'ليبيا', 'TN': 'تونس', 'DZ': 'الجزائر',
            'MA': 'المغرب', 'SD': 'السودان', 'SO': 'الصومال',
            'US': 'الولايات المتحدة', 'GB': 'المملكة المتحدة', 'DE': 'ألمانيا',
            'FR': 'فرنسا', 'IT': 'إيطاليا', 'ES': 'إسبانيا', 'NL': 'هولندا',
            'TR': 'تركيا', 'IR': 'إيران', 'PK': 'باكستان', 'IN': 'الهند',
            'ID': 'إندونيسيا', 'MY': 'ماليزيا', 'PH': 'الفلبين',
            'CN': 'الصين', 'JP': 'اليابان', 'KR': 'كوريا',
            'CA': 'كندا', 'AU': 'أستراليا', 'BR': 'البرازيل',
            'RU': 'روسيا', 'UA': 'أوكرانيا', 'NG': 'نيجيريا',
        }
        country_name = COUNTRY_NAMES.get(country_code, country)

        visitor = {
            'ip': ip, 'country': country_name, 'country_code': country_code,
            'user_agent': ua, 'device_type': device_type,
            'browser': browser, 'os': os_name, 'page': request.path
        }
        asyncio.run(db.record_web_visitor(visitor))
    except Exception:
        pass  # Never fail a request because of tracking


@app.route('/')
def index():
    """Main download page - adapts to platform via subdomain"""
    return render_template('index.html', platform=g.get("platform", DEFAULT_PLATFORM))


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    health = {
        "status": "ok",
        "service": "istxbot-web",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    # Check database
    try:
        asyncio.run(db.get_stats())
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {str(e)[:100]}"
        health["status"] = "degraded"
    # Check bot process
    try:
        bot = get_bot()
        health["checks"]["bot"] = "connected" if bot else "not_initialized"
    except Exception as e:
        health["checks"]["bot"] = f"error: {str(e)[:100]}"
        health["status"] = "degraded"
    status_code = 200 if health["status"] == "ok" else 503
    return jsonify(health), status_code

@app.route('/help')
def help_page():
    """Usage guide page"""
    return render_template('help.html')


@app.route('/contact')
def contact_page():
    """Contact page"""
    phone = os.getenv("SUPPORT_PHONE", "966XXXXXXXXX")
    return render_template('contact.html', phone=phone)


@app.route('/account')
def account_page():
    """Account page - key recovery & subscription"""
    return render_template('account.html')


@app.route('/sw.js')
def service_worker():
    """Serve service worker at root scope"""
    return app.send_static_file('sw.js')


@app.route('/api/bot/webhook', methods=['POST'])
def bot_webhook():
    """Receive Telegram updates via webhook"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "No data"}), 400
    try:
        process_update(data)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})


@app.route('/api/download', methods=['POST'])
def api_download():
    """API endpoint to download a video using an activation key (platform-aware)"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "بيانات غير صالحة"}), 400

    url = (data.get('url') or '').strip()
    key = (data.get('key') or '').strip()
    platform = g.get("platform", DEFAULT_PLATFORM)

    if not url:
        return jsonify({"success": False, "error": f"الرجاء إدخال رابط {platform}"}), 400

    try:
        result = asyncio.run(_process_download(url, key, platform))
        if not result.get("success"):
            return jsonify(result), 400

        filepath = result.get("filepath", "")
        if not filepath or not os.path.exists(filepath):
            logger.error(f"File not found after download: {filepath}")
            return jsonify({"success": False, "error": "فشل تحميل الفيديو. تأكد من الرابط."}), 400

        filename = result.get("filename", f"{platform.lower()}.mp4")
        mime_type = "video/mp4"
        ext = os.path.splitext(filename)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            mime_type = f"image/{ext[1:]}"
            if ext == '.jpg':
                mime_type = "image/jpeg"

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"Cleaned up: {filepath}")
            except Exception as e:
                logger.error(f"Error cleaning up file: {e}")
            return response

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype=mime_type
        )

    except Exception as e:
        logger.error(f"Unexpected error in api_download: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"فشل التحميل من {platform}. تأكد من صحة الرابط."}), 500


def get_wp_option(key, default=None):
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=os.getenv('WP_DB_HOST', 'localhost'),
            user=os.getenv('WP_DB_USER', 'tiktok_wp'),
            password=os.getenv('WP_DB_PASS', 'Tk_wp_2026_Secure!'),
            database=os.getenv('WP_DB_NAME', 'tiktok_wp')
        )
        c = conn.cursor()
        c.execute("SELECT option_value FROM twp_options WHERE option_name=%s", (key,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except:
        pass
    return default

def get_daily_download_limit():
    val = get_wp_option('tk_bot_free_downloads', '3')
    try: return int(val)
    except: return 3

def get_reset_hour():
    return 0

async def _process_download(url: str, key: str, platform: str = "TikTok") -> dict:
    """Process download: auto-generate key, check limits, download video"""
    downloader = _get_downloader(platform)
    from flask import request as req

    # 1. Auto-generate device key (5 downloads/day)
    device_ip = (
        req.headers.get('CF-Connecting-IP') or
        req.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
        req.remote_addr or
        'unknown'
    )
    device_ua = req.headers.get('User-Agent', '')[:80]
    device_id = f"{platform}:{device_ip}:{device_ua}"
    
    if not key:
        kr = await db.get_or_create_device_key(device_id, daily_limit=get_daily_download_limit(), platform=platform)
        if not kr.get('success'):
            return {"success": False, "error": kr.get('message', 'غير متاح')}
        key = kr['key']
    
    # 2. Consume key & track device usage
    consumed = await db.consume_activation_key(key)
    if consumed:
        await db.consume_device_key(device_id, key)
    else:
        kr2 = await db.get_or_create_device_key(device_id, daily_limit=get_daily_download_limit(), platform=platform)
        if kr2.get('success'):
            key = kr2['key']
            await db.consume_activation_key(key)
            await db.consume_device_key(device_id, key)
        else:
            return {"success": False, "error": kr2.get('message', 'استهلكت الحد اليومي')}

    # 2. Validate URL
    is_valid, error_msg = await downloader.check_url_valid(url)
    if not is_valid:
        return {"success": False, "error": error_msg or f"رابط {platform} غير صالح"}

    # 3. Download the video
    try:
        success, files, title = await downloader.download(url)
    except Exception as e:
        logger.error(f"Download error: {e}")
        return {"success": False, "error": f"فشل تحميل الفيديو من {platform}"}

    if not success or not files:
        error_msg = title if title and "❌" in title else "فشل تحميل الفيديو. تأكد من الرابط وحاول مرة أخرى."
        return {"success": False, "error": error_msg}

    filepath = files[0]
    if not os.path.exists(filepath):
        return {"success": False, "error": "لم يتم العثور على الملف بعد التحميل"}



    # 5. Record download for stats
    try:
        file_size = os.path.getsize(filepath)
        await db.record_download(
            user_id=0,
            platform=platform,
            title=title or platform,
            file_size=file_size,
            file_path=filepath
        )
    except Exception as e:
        logger.error(f"Failed to record download: {e}")

    safe_title = title or platform
    safe_title = "".join(c for c in safe_title if c.isalnum() or c in ' _-')
    safe_title = safe_title[:50] or platform
    ext = os.path.splitext(filepath)[1] or '.mp4'
    filename = f"{safe_title}{ext}"

    return {
        "success": True,
        "filepath": filepath,
        "filename": filename,
        "title": title
    }


@app.route('/api/validate-key', methods=['POST'])
def api_validate_key():
    """Check if an activation key is valid (for real-time validation in frontend)"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"valid": False, "message": "بيانات غير صالحة"}), 400

    key = (data.get('key') or '').strip()
    if not key:
        return jsonify({"valid": False, "message": "الرجاء إدخال مفتاح التفعيل"}), 400

    result = asyncio.run(db.validate_activation_key(key, g.get("platform", DEFAULT_PLATFORM)))
    return jsonify(result)


@app.route('/api/free-key', methods=['POST'])
def api_free_key():
    """Generate a free temporary key for the device (24h, 5 downloads)"""
    device_ip = (
        request.headers.get('CF-Connecting-IP') or
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
        request.remote_addr or
        'unknown'
    )
    device_ua = request.headers.get('User-Agent', '')[:80]
    platform = g.get("platform", DEFAULT_PLATFORM)
    device_id = f"{platform}:{device_ip}:{device_ua}"

    result = asyncio.run(db.get_or_create_device_key(device_id, daily_limit=get_daily_download_limit(), platform=g.get("platform", DEFAULT_PLATFORM)))
    return jsonify(result)


@app.route('/api/recover-key', methods=['POST'])
def api_recover_key():
    """Recover activation keys by registered email with OTP verification"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400

    email = (data.get('email') or '').strip().lower()
    otp = (data.get('otp') or '').strip()

    if not email or '@' not in email:
        return jsonify({"success": False, "message": "الرجاء إدخال بريد إلكتروني صحيح"}), 400

    # Step 2: verify OTP and return keys
    if otp:
        stored = _email_otp.get(email, {})
        if stored.get('otp') != otp:
            return jsonify({"success": False, "message": "رمز OTP غير صحيح"})
        if (datetime.now() - stored.get('time', datetime.now())).total_seconds() > 300:
            _email_otp.pop(email, None)
            return jsonify({"success": False, "message": "انتهت صلاحية الرمز"})

        _email_otp.pop(email, None)
        keys = asyncio.run(db.find_keys_by_owner(email))
        if not keys:
            return jsonify({"success": False, "message": "لم يتم العثور على مفاتيح بهذا البريد"})
        return jsonify({"success": True, "keys": keys, "count": len(keys)})

    # Step 1: check email exists in system, then send OTP
    keys = asyncio.run(db.find_keys_by_owner(email))
    if not keys:
        return jsonify({"success": False, "message": "لا توجد مفاتيح مسجلة بهذا البريد"})

    import random
    code = str(random.randint(100000, 999999))
    _email_otp[email] = {'otp': code, 'time': datetime.now()}

    sent = send_email_otp(email, code)
    if sent:
        return jsonify({"success": True, "require_otp": True, "message": "تم إرسال رمز التحقق إلى بريدك"})

    # SMTP fallback: send OTP to admin via Telegram
    notify = f"📧 <b>OTP استرجاع</b>\n\nالبريد: {email}\nالرمز: <code>{code}</code>"
    send_telegram_notification(notify)
    return jsonify({"success": True, "require_otp": True, "message": "تم إرسال رمز التحقق. تحقق من بريدك أو تواصل مع الدعم."})


@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    """Submit a subscription request with anti-bot protection"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400

    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip()
    ts = int(data.get('ts') or 0)

    # ── Anti-bot: Honeypot ──
    hp = (data.get('hp') or '').strip()
    if hp:
        logger.warning(f"Bot detected (honeypot filled): {hp[:50]}")
        return jsonify({"success": False, "message": "تم تقديم الطلب"})  # fake success

    # ── Anti-bot: Timing check (form submitted between 3 and 600 seconds) ──
    now_ts = int(datetime.now().timestamp() * 1000)
    age_ms = now_ts - ts if ts else 0
    if ts and (age_ms < 3000 or age_ms > 600000):
        logger.warning(f"Suspicious timing: {age_ms}ms")
        return jsonify({"success": False, "message": "يرجى الانتظار لحظة ثم المحاولة"}), 400

    # ── Validation ──
    if not email or '@' not in email or len(email) > 100:
        return jsonify({"success": False, "message": "الرجاء إدخال بريد إلكتروني صحيح"}), 400
    if len(name) > 60:
        return jsonify({"success": False, "message": "الاسم طويل جداً"}), 400

    # ── Anti-duplicate: check existing ──
    async def _check_dup(e):
        subs = await db.get_subscription_requests("new")
        for s in subs:
            if s.get('email') == e:
                return True
        return False

    if asyncio.run(_check_dup(email)):
        return jsonify({"success": False, "message": "لديك طلب اشتراك قيد المراجعة بالفعل"}), 409

    # ── Submit ──
    success = asyncio.run(db.create_subscription_request(email, name))
    if success:
        notify_text = (
            f"📩 <b>طلب اشتراك جديد</b>\n\n"
            f"👤 الاسم: {name or 'غير محدد'}\n"
            f"📧 البريد: {email}\n"
            f"🕐 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        send_telegram_notification(notify_text)

        # Send confirmation email to user
        confirm_html = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:400px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:#fe2c55">📩 تم استلام طلبك</h2>
<p style="color:#ccc;font-size:14px;line-height:1.8">مرحباً {name or 'بك'}،</p>
<p style="color:#ccc;font-size:14px;line-height:1.8">تم استلام طلب اشتراكك بنجاح. ستصلك رسالة قريباً لتفعيل اشتراكك.</p>
<div style="margin:20px 0;padding:12px;background:rgba(254,44,85,0.08);border-radius:8px;border:1px solid rgba(254,44,85,0.1)">
<p style="color:#888;font-size:12px;margin:0">للاستفسار العاجل:</p>
<p style="color:#ccc;font-size:13px;margin:6px 0 0">تيليجرام: @qazvvx</p>
</div>
<p style="color:#555;font-size:11px;margin-top:24px">تحياتنا — فريق istx.io</p>
</div></body></html>"""
        send_subscription_email(email, "تم استلام طلب الاشتراك - istx.io", confirm_html)

        return jsonify({"success": True, "message": "تم استلام طلبك بنجاح. سيتم التواصل معك قريباً."})
    return jsonify({"success": False, "message": "حدث خطأ. حاول مرة أخرى."}), 500


@app.route('/api/subscription-status', methods=['POST'])
def api_subscription_status():
    """Check subscription request status by email"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400

    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "بريد غير صحيح"}), 400

    async def _check():
        subs = await db.get_subscription_requests("new")
        for s in subs:
            if s.get('email') == email:
                return s
        # Check active subscriptions
        subs_active = await db.get_subscription_requests("active")
        for s in subs_active:
            if s.get('email') == email:
                return s
        # Check dismissed
        subs_done = await db.get_subscription_requests("done")
        for s in subs_done:
            if s.get('email') == email:
                return s
        return None

    sub = asyncio.run(_check())
    if sub:
        status_map = {"new": "قيد المراجعة", "active": "مفعل", "done": "مرفوض", "dismissed": "مرفوض"}
        return jsonify({
            "success": True,
            "found": True,
            "status": sub.get("status", "new"),
            "status_text": status_map.get(sub.get("status", "new"), sub.get("status", "new")),
            "created_at": sub.get("created_at", ""),
            "name": sub.get("name", "")
        })
    return jsonify({"success": True, "found": False, "message": "لا يوجد طلب اشتراك لهذا البريد"})



# ─── Web Rewards / Points ───────────────────────────────────────

@app.route('/api/web/get-reward-link', methods=['POST'])
def api_get_reward_link():
    """Generate a reward visit link for a user"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "بريد غير صحيح"}), 400
    points = int(data.get('points', 5))
    token = asyncio.run(db.create_reward_token(email, points))
    if not token:
        return jsonify({"success": False, "message": "حدث خطأ"}), 500
    domain = os.getenv("REWARD_DOMAIN", "istx.io")
    link = f"https://{domain}/reward/{token}"
    return jsonify({"success": True, "link": link, "token": token, "points": points})


@app.route('/reward/<token>')
def reward_landing(token):
    """Landing page that awards points and redirects back"""
    email = request.args.get('email', '')
    if not email:
        return render_template('reward.html', token=token, email='', claimed=False, message='')
    result = asyncio.run(db.claim_reward_visit(email, token))
    if result.get('success'):
        points = result.get('points_earned', 0)
        bal = asyncio.run(db.get_web_points(email))
        total = bal.get('points', 0)
        email_html = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:420px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:#25f4ee">🎁 تمت إضافة نقاط إلى حسابك</h2>
<div style="font-size:40px;font-weight:800;color:#fe2c55;margin:16px 0">+{points}</div>
<p style="color:#ccc;font-size:14px;line-height:1.8">تمت إضافة <b>{points}</b> نقاط مكافأة إلى رصيدك.<br>رصيدك الحالي: <b style="color:#25f4ee">{total} نقطة</b></p>
<p style="color:#888;font-size:13px;line-height:1.7">يمكنك استبدال 10 نقاط = تحميلة إضافية واحدة من صفحة حسابك.</p>
<a href="https://inspiredownloader.com/account/" style="display:inline-block;margin-top:12px;padding:12px 28px;background:#fe2c55;color:#fff;text-decoration:none;border-radius:8px;font-weight:700;font-size:14px">💰 تفقد رصيدك الآن</a>
<p style="color:#555;font-size:11px;margin-top:24px">فريق istx.io — شكراً لاستخدامك خدماتنا</p>
</div></body></html>"""
        send_subscription_email(email, "🎁 تمت إضافة نقاط إلى حسابك", email_html)
    return render_template('reward.html', token=token, email=email,
                          claimed=result.get('success', False),
                          points_earned=result.get('points_earned', 0),
                          message=result.get('message', ''))


@app.route('/api/web/claim-reward', methods=['POST'])
def api_claim_reward():
    """Claim reward points from a visit token"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400
    email = (data.get('email') or '').strip().lower()
    token = (data.get('token') or '').strip()
    if not email or not token:
        return jsonify({"success": False, "message": "بيانات غير مكتملة"}), 400
    result = asyncio.run(db.claim_reward_visit(email, token))
    if result.get('success'):
        points = result.get('points_earned', 0)
        bal = asyncio.run(db.get_web_points(email))
        total = bal.get('points', 0)
        email_html = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:420px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:#25f4ee">🎁 تمت إضافة نقاط إلى حسابك</h2>
<div style="font-size:40px;font-weight:800;color:#fe2c55;margin:16px 0">+{points}</div>
<p style="color:#ccc;font-size:14px;line-height:1.8">تمت إضافة <b>{points}</b> نقاط مكافأة إلى رصيدك.<br>رصيدك الحالي: <b style="color:#25f4ee">{total} نقطة</b></p>
<p style="color:#888;font-size:13px;line-height:1.7">يمكنك استبدال 10 نقاط = تحميلة إضافية واحدة من صفحة حسابك.</p>
<a href="https://inspiredownloader.com/account/" style="display:inline-block;margin-top:12px;padding:12px 28px;background:#fe2c55;color:#fff;text-decoration:none;border-radius:8px;font-weight:700;font-size:14px">💰 تفقد رصيدك الآن</a>
<p style="color:#555;font-size:11px;margin-top:24px">فريق istx.io — شكراً لاستخدامك خدماتنا</p>
</div></body></html>"""
        send_subscription_email(email, "🎁 تمت إضافة نقاط إلى حسابك", email_html)
    return jsonify(result)


@app.route('/api/web/points', methods=['POST'])
def api_web_points():
    """Get user points balance"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "بريد غير صحيح"}), 400
    result = asyncio.run(db.get_web_points(email))
    return jsonify({"success": True, **result})


@app.route('/api/web/redeem-points', methods=['POST'])
def api_redeem_points():
    """Redeem points for extra downloads"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400
    email = (data.get('email') or '').strip().lower()
    key_value = (data.get('key') or '').strip()
    points = int(data.get('points', 0))
    if not email or not key_value or points < 10:
        return jsonify({"success": False, "message": "بيانات غير مكتملة"}), 400
    result = asyncio.run(db.redeem_web_points(email, points, key_value))
    return jsonify(result)

ADMIN_PATH = os.getenv("ADMIN_PATH", "cp-" + os.urandom(4).hex())

# OTP store (in-memory)
_otp_store = {}
_otp_cleanup_time = 0


@app.route('/' + ADMIN_PATH)
def admin_page():
    """Admin dashboard"""
    return render_template('admin.html')


def _require_admin():
    """Check admin session token from header"""
    token = request.headers.get('X-Admin-Token', '')
    if not token:
        return False
    return asyncio.run(db.validate_admin_session(token))


# Auth
@app.route('/api/admin/request-otp', methods=['POST'])
def admin_request_otp():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400

    password = data.get('password', '')
    if not asyncio.run(db.verify_admin_password(password)):
        return jsonify({"success": False, "message": "كلمة مرور غير صحيحة"}), 401

    import random
    otp = str(random.randint(100000, 999999))
    _otp_store[otp] = (datetime.now(), 3)  # 3 attempts

    notify_text = f"🔐 <b>رمز OTP</b>\n\n<code>{otp}</code>\n\nينتهي خلال 5 دقائق"
    send_telegram_notification(notify_text)

    return jsonify({"success": True, "message": "تم إرسال رمز OTP"})


@app.route('/api/admin/verify-otp', methods=['POST'])
def admin_verify_otp():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400

    otp = data.get('otp', '')
    entry = _otp_store.get(otp)
    if not entry:
        return jsonify({"success": False, "message": "رمز OTP غير صحيح أو منتهي"}), 401

    created, attempts = entry
    if (datetime.now() - created).total_seconds() > 300:
        del _otp_store[otp]
        return jsonify({"success": False, "message": "انتهت صلاحية الرمز"}), 401

    import secrets
    token = secrets.token_hex(32)
    asyncio.run(db.create_admin_session(token))

    del _otp_store[otp]
    return jsonify({"success": True, "token": token})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    token = request.headers.get('X-Admin-Token', '')
    if token:
        asyncio.run(db.delete_admin_session(token))
    return jsonify({"success": True})


# Data APIs
@app.route('/api/admin/check-session', methods=['GET'])
def admin_check_session():
    if not _require_admin():
        return jsonify({"success": False}), 401
    return jsonify({"success": True})

@app.route('/api/admin/stats', methods=['POST'])
def admin_stats():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    stats = asyncio.run(db.get_admin_stats())
    return jsonify({"success": True, **stats})


@app.route('/api/admin/keys', methods=['POST'])
def admin_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    keys = asyncio.run(db.get_all_activation_keys())
    return jsonify({"success": True, "keys": keys})


@app.route('/api/admin/create-keys', methods=['POST'])
def admin_create_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400

    owner = data.get('owner', '').strip().lower()
    limit = int(data.get('limit', 10))
    count = int(data.get('count', 1))
    notes = data.get('notes', '').strip()
    platform = data.get('platform', 'TikTok').strip()

    import secrets

    KEY_PREFIXES = {"TikTok": "ttk-"}

    async def _create():
        created = []
        for _ in range(count):
            prefix = KEY_PREFIXES.get(platform, "k-")
            key = prefix + secrets.token_hex(4)
            ok = await db.create_activation_key(key=key, owner_name=owner, usage_limit=limit, notes=notes, platform=platform)
            if ok:
                created.append(key)
        return created

    keys = asyncio.run(_create())
    if keys:
        # Send email notification if owner is an email address
        if owner and '@' in owner:
            try:
                key_list_html = ''.join(f'<div style="background:#16213e;border:1px solid #2a2a4a;border-radius:8px;padding:12px;margin:8px 0;direction:ltr;font-family:monospace;font-size:16px;color:#fff;text-align:center">🔑 {k}</div>' for k in keys)
                platform_name = {"TikTok": "TikTok"}.get(platform, platform)
                body_html = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:420px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:{'#fe2c55'}">✅ تم إنشاء مفتاح {platform_name}</h2>
<p style="color:#ccc;font-size:14px;line-height:1.8">مرحباً، مفتاح التفعيل الخاص بك لمنصة {platform_name}:</p>
{key_list_html}
<div style="background:rgba(254,44,85,0.08);border-radius:8px;padding:12px;margin-top:12px">
<p style="color:#888;font-size:13px;margin:0">📊 حد التحميلات: <b style="color:#fff">{limit}</b></p>
<p style="color:#888;font-size:13px;margin:4px 0 0">🔗 رابط التحميل: <a href="https://{platform.lower()}.istx.io" style="color:#25f4ee">https://{platform.lower()}.istx.io</a></p>
</div>
<p style="color:#555;font-size:11px;margin-top:24px">تحياتنا — فريق istx.io</p>
</div></body></html>"""
                send_subscription_email(owner, f"مفتاح تفعيل {platform_name} - istx.io", body_html)
                logger.info(f"Key email sent to {owner} for {platform}")
            except Exception as e:
                logger.error(f"Failed to send key email: {e}")
        return jsonify({"success": True, "message": f"تم إنشاء {len(keys)} مفتاح لـ {platform}" + (f" وإرسالها إلى {owner}" if owner and '@' in owner else ""), "keys": keys})
    return jsonify({"success": False, "message": "فشل إنشاء المفاتيح"}), 500


@app.route('/api/admin/toggle-key', methods=['POST'])
def admin_toggle_key():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False}), 400
    asyncio.run(db.toggle_activation_key(data.get('key', ''), bool(data.get('active', True))))
    return jsonify({"success": True})


@app.route('/api/admin/delete-key', methods=['POST'])
def admin_delete_key():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False}), 400
    asyncio.run(db.delete_activation_key(data.get('key', '')))
    return jsonify({"success": True})


@app.route('/api/admin/update-key', methods=['POST'])
def admin_update_key():
    """Update key usage count and/or limit"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "بيانات غير صالحة"}), 400
    key = data.get('key', '').strip()
    count = data.get('usage_count')
    limit = data.get('usage_limit')
    if count is not None:
        count = int(count)
    if limit is not None:
        limit = int(limit)
    if not key or (count is None and limit is None):
        return jsonify({"success": False, "message": "بيانات غير مكتملة"}), 400
    ok = asyncio.run(db.update_activation_key(key, usage_count=count, usage_limit=limit))
    if ok:
        return jsonify({"success": True, "message": "تم التحديث"})
    return jsonify({"success": False, "message": "حدث خطأ"}), 500


@app.route('/api/admin/subscriptions', methods=['POST'])
def admin_subscriptions():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    requests_list = asyncio.run(db.get_subscription_requests("new"))
    return jsonify({"success": True, "requests": requests_list})


@app.route('/api/admin/activate-subscription', methods=['POST'])
def admin_activate_subscription():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False}), 400

    email = (data.get('email') or '').strip().lower()
    limit = int(data.get('limit', 50))
    req_id = int(data.get('id', 0))
    platform = data.get('platform', 'TikTok').strip()

    import secrets
    KEY_PREFIXES = {"TikTok": "ttk-"}
    prefix = KEY_PREFIXES.get(platform, "k-")
    key = prefix + secrets.token_hex(4)

    async def _activate():
        ok = await db.create_activation_key(key=key, owner_name=email, usage_limit=limit, notes="اشتراك مفعل", platform=platform)
        if ok and req_id:
            await db.update_subscription_status(req_id, "active")
        return ok

    ok = asyncio.run(_activate())
    if ok:
        # Send the key to the user's email (platform-aware)
        accent = '#fe2c55'
        domain = f"{platform.lower()}.istx.io"
        platform_name = {"TikTok": "TikTok"}.get(platform, platform)
        key_html = f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:420px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:{accent}">✅ تم تفعيل اشتراكك - {platform_name}</h2>
<p style="color:#ccc;font-size:14px;line-height:1.8">شكراً لاشتراكك. مفتاح التفعيل الخاص بك لمنصة {platform_name}:</p>
<div style="background:#16213e;border:1px solid #2a2a4a;border-radius:10px;padding:16px;margin:16px 0">
<span style="font-family:monospace;font-size:20px;font-weight:800;color:#fff;letter-spacing:2px;direction:ltr;display:inline-block">🔑 {key}</span>
</div>
<p style="color:#888;font-size:13px;line-height:1.7">عدد التحميلات: <b style="color:#fff">{limit}</b><br>انسخ المفتاح واستخدمه في صفحة التحميل.</p>
<a href="https://{domain}" style="display:inline-block;margin-top:12px;padding:12px 28px;background:{accent};color:#000;text-decoration:none;border-radius:8px;font-weight:700;font-size:14px">📥 ابدأ التحميل</a>
<p style="color:#555;font-size:11px;margin-top:24px">للتواصل: تيليجرام @qazvvx — تحياتنا</p>
</div></body></html>"""
        send_subscription_email(email, f"تم تفعيل اشتراكك - مفتاح: {key}", key_html)

        return jsonify({
            "success": True,
            "message": f"تم تفعيل الاشتراك وإرسال المفتاح إلى {email}",
            "key": key,
            "email": email
        })
    return jsonify({"success": False, "message": "حدث خطأ"}), 500


@app.route('/api/admin/dismiss-subscription', methods=['POST'])
def admin_dismiss_subscription():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False}), 400
    asyncio.run(db.update_subscription_status(int(data.get('id', 0)), "done"))
    return jsonify({"success": True})


@app.route('/api/admin/visitor-stats', methods=['POST'])
def admin_visitor_stats():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    stats = asyncio.run(db.get_web_visitor_stats())
    recent = asyncio.run(db.get_recent_web_visitors(30))
    return jsonify({"success": True, "stats": stats, "recent": recent})


@app.route('/api/admin/site-settings', methods=['POST'])
def admin_site_settings():
    """Get or update site branding settings (with platform support)"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}

    platform = data.get('platform', '')  # 'TikTok' or '' for global
    prefix = f"{platform}:" if platform else ""

    # If 'settings' key present, save platform-scoped
    if 'settings' in data:
        saved = 0
        for key, value in data['settings'].items():
            if not isinstance(value, str):
                continue
            db_key = prefix + key
            ok = asyncio.run(db.set_site_setting(db_key, value))
            if ok:
                saved += 1
        return jsonify({"success": True, "message": f"تم حفظ {saved} إعداد لـ {platform or 'العامة'}"})

    # Return settings filtered by platform
    settings_dict = asyncio.run(db.get_all_site_settings())
    result = {}
    for k, v in settings_dict.items():
        if platform:
            if k.startswith(prefix):
                result[k[len(prefix):]] = v
        else:
            if not k.startswith('TikTok:'):
                result[k] = v
    # Merge with platform defaults
    if platform:
        defaults = _PLATFORM_CONFIGS.get(platform, {})
        merged = {**defaults, **result}
        return jsonify({"success": True, "settings": merged, "platform": platform})
    else:
        merged = {**_DEFAULT_SITE_SETTINGS, **result}
        return jsonify({"success": True, "settings": merged, "platform": "global"})


@app.route('/api/admin/upload-logo', methods=['POST'])
def admin_upload_logo():
    """Upload a logo image file and save it to static folder"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    if 'logo' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرسال ملف"}), 400

    file = request.files['logo']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "ملف فارغ"}), 400

    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'):
        return jsonify({"success": False, "message": "الصيغ المسموحة: png, jpg, svg, webp, gif"}), 400

    # Save with fixed name
    static_dir = os.path.join(APP_DIR, 'static')
    logo_name = f"logo_custom{ext}"
    save_path = os.path.join(static_dir, logo_name)

    try:
        file.save(save_path)
        logo_url = f"/static/{logo_name}"
        # Save to settings
        asyncio.run(db.set_site_setting('logo_url', logo_url))
        asyncio.run(db.set_site_setting('logo_type', 'image' if ext != '.svg' else 'svg'))
        return jsonify({"success": True, "message": "تم رفع الشعار", "url": logo_url})
    except Exception as e:
        logger.error(f"Error uploading logo: {e}")
        return jsonify({"success": False, "message": "فشل رفع الملف"}), 500


@app.route('/api/admin/delete-logo', methods=['POST'])
def admin_delete_logo():
    """Delete custom logo and revert to default"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    try:
        static_dir = os.path.join(APP_DIR, 'static')
        for name in ('logo_custom.png', 'logo_custom.jpg', 'logo_custom.jpeg',
                     'logo_custom.svg', 'logo_custom.webp', 'logo_custom.gif'):
            path = os.path.join(static_dir, name)
            if os.path.exists(path):
                os.remove(path)
        asyncio.run(db.set_site_setting('logo_url', ''))
        asyncio.run(db.set_site_setting('logo_type', 'svg'))
        return jsonify({"success": True, "message": "تم حذف الشعار واستعادة الافتراضي"})
    except Exception as e:
        logger.error(f"Error deleting logo: {e}")
        return jsonify({"success": False, "message": "فشل الحذف"}), 500


@app.route('/api/admin/upload-banner-icon', methods=['POST'])
def admin_upload_banner_icon():
    """Upload a banner icon image file and save it to static folder"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    if 'icon' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرسال ملف"}), 400

    file = request.files['icon']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "ملف فارغ"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'):
        return jsonify({"success": False, "message": "الصيغ المسموحة: png, jpg, svg, webp, gif"}), 400

    static_dir = os.path.join(APP_DIR, 'static')
    icon_name = f"banner_icon_custom{ext}"
    save_path = os.path.join(static_dir, icon_name)

    try:
        file.save(save_path)
        icon_url = f"/static/{icon_name}"
        asyncio.run(db.set_site_setting('banner_icon_url', icon_url))
        return jsonify({"success": True, "message": "تم رفع أيقونة البنر", "url": icon_url})
    except Exception as e:
        logger.error(f"Error uploading banner icon: {e}")
        return jsonify({"success": False, "message": "فشل رفع الملف"}), 500


@app.route('/api/admin/delete-banner-icon', methods=['POST'])
def admin_delete_banner_icon():
    """Delete custom banner icon and revert to default"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    try:
        static_dir = os.path.join(APP_DIR, 'static')
        for name in ('banner_icon_custom.png', 'banner_icon_custom.jpg', 'banner_icon_custom.jpeg',
                     'banner_icon_custom.svg', 'banner_icon_custom.webp', 'banner_icon_custom.gif'):
            path = os.path.join(static_dir, name)
            if os.path.exists(path):
                os.remove(path)
        asyncio.run(db.set_site_setting('banner_icon_url', ''))
        return jsonify({"success": True, "message": "تم حذف أيقونة البنر واستعادة الافتراضي"})
    except Exception as e:
        logger.error(f"Error deleting banner icon: {e}")
        return jsonify({"success": False, "message": "فشل الحذف"}), 500


@app.route('/api/admin/upload-contact-icon', methods=['POST'])
def admin_upload_contact_icon():
    """Upload a contact channel icon image"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    channel = request.form.get('channel', 'whatsapp')
    if channel not in ('whatsapp', 'telegram'):
        return jsonify({"success": False, "message": "قناة غير صالحة"}), 400

    if 'icon' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرسال ملف"}), 400

    file = request.files['icon']
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "ملف فارغ"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.svg', '.webp'):
        return jsonify({"success": False, "message": "الصيغ المسموحة: png, jpg, svg, webp"}), 400

    static_dir = os.path.join(APP_DIR, 'static')
    icon_name = f"contact_{channel}{ext}"
    save_path = os.path.join(static_dir, icon_name)

    try:
        file.save(save_path)
        icon_url = f"/static/{icon_name}"
        setting_key = f"contact_{channel}_icon"
        asyncio.run(db.set_site_setting(setting_key, icon_url))
        return jsonify({"success": True, "message": f"تم رفع أيقونة {channel}", "url": icon_url})
    except Exception as e:
        logger.error(f"Error uploading contact icon: {e}")
        return jsonify({"success": False, "message": "فشل رفع الملف"}), 500


@app.route('/api/admin/delete-contact-icon', methods=['POST'])
def admin_delete_contact_icon():
    """Delete a custom contact channel icon"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    data = request.get_json(silent=True) or {}
    channel = data.get('channel', 'whatsapp')
    if channel not in ('whatsapp', 'telegram'):
        return jsonify({"success": False, "message": "قناة غير صالحة"}), 400

    try:
        static_dir = os.path.join(APP_DIR, 'static')
        for ext in ('.png', '.jpg', '.jpeg', '.svg', '.webp'):
            path = os.path.join(static_dir, f"contact_{channel}{ext}")
            if os.path.exists(path):
                os.remove(path)
        setting_key = f"contact_{channel}_icon"
        asyncio.run(db.set_site_setting(setting_key, ''))
        return jsonify({"success": True, "message": f"تم حذف أيقونة {channel}"})
    except Exception as e:
        logger.error(f"Error deleting contact icon: {e}")
        return jsonify({"success": False, "message": "فشل الحذف"}), 500


@app.route('/api/admin/change-password', methods=['POST'])
def admin_change_password():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False}), 400

    password = data.get('password', '')
    if len(password) < 6:
        return jsonify({"success": False, "message": "كلمة المرور 6 أحرف على الأقل"})

    import hashlib, tempfile
    new_hash = hashlib.sha256(password.encode()).hexdigest()
    # Write to .env file atomically
    env_path = os.path.join(BASE_DIR, '.env')
    try:
        with open(env_path, 'r') as f:
            content = f.read()
        if 'ADMIN_PASSWORD_HASH' in content:
            content = os.linesep.join([
                line if not line.startswith('ADMIN_PASSWORD_HASH=') else f'ADMIN_PASSWORD_HASH={new_hash}'
                for line in content.splitlines()
            ])
        else:
            content += f'\nADMIN_PASSWORD_HASH={new_hash}\n'
        # Atomic write: write to temp file then rename
        tmp_path = env_path + '.tmp'
        with open(tmp_path, 'w') as f:
            f.write(content)
        os.replace(tmp_path, env_path)
        return jsonify({"success": True, "message": "تم تغيير كلمة المرور بنجاح"})
    except Exception as e:
        logger.error(f"Error writing password: {e}")
        return jsonify({"success": False, "message": "حدث خطأ في حفظ كلمة المرور"}), 500

# ─── Dashboard API ─────────────────────────────────────────────────

@app.route('/api/admin/dashboard', methods=['POST'])
def admin_dashboard():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    stats = asyncio.run(db.get_dashboard_stats())
    return jsonify({"success": True, **stats})


@app.route('/api/admin/download-logs', methods=['POST'])
def admin_download_logs():
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    page = int(data.get('page', 1))
    platform = data.get('platform', '')
    result = asyncio.run(db.get_download_logs(page=page, platform=platform))
    return jsonify({"success": True, **result})


@app.route('/api/admin/download-trends', methods=['POST'])
def admin_download_trends():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    days = int(data.get('days', 14))
    trends = asyncio.run(db.get_download_trends(days))
    return jsonify({"success": True, "trends": trends})


@app.route('/api/admin/search-keys', methods=['POST'])
def admin_search_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()
    platform = data.get('platform', '').strip()
    keys = asyncio.run(db.search_keys(query=query, platform=platform))
    return jsonify({"success": True, "keys": keys})


@app.route('/api/admin/export-keys', methods=['POST'])
def admin_export_keys():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    csv_data = asyncio.run(db.export_keys_csv())
    from flask import Response
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=keys_export.csv"}
    )


@app.route('/api/admin/ads-settings', methods=['POST'])
def admin_ads_settings():
    """Get or update ads HTML code (top, middle, bottom)"""
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}

    if 'settings' in data:
        saved = 0
        for k, v in data['settings'].items():
            ok = asyncio.run(db.set_site_setting(f"ads:{k}", str(v)))
            if ok:
                saved += 1
        return jsonify({"success": True, "message": f"تم حفظ {saved} إعداد إعلاني"})

    all_settings = asyncio.run(db.get_all_site_settings())
    ads_settings = {}
    for k, v in all_settings.items():
        if k.startswith("ads:"):
            ads_settings[k[4:]] = v
    return jsonify({"success": True, "settings": ads_settings})


@app.route('/api/admin/landing-page', methods=['POST'])
def admin_landing_page():
    if not _require_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    if 'settings' in data:
        saved = 0
        for k, v in data['settings'].items():
            ok = asyncio.run(db.set_landing_page_setting(k, v))
            if ok: saved += 1
        return jsonify({"success": True, "message": f"تم حفظ {saved} إعداد للصفحة الرئيسية"})
    settings = asyncio.run(db.get_landing_page_settings())
    return jsonify({"success": True, "settings": settings})


def _require_bot_admin():
    """Check admin auth for bot control - token, password, or API key"""
    data = request.get_json(silent=True) or {}
    api_key = (data.get('api_key') or '').strip()
    if api_key and api_key == os.getenv('BOT_API_KEY', 'istx_bot_secret_2026_key'):
        return True
    pwd = (data.get('password') or '').strip()
    if pwd and asyncio.run(db.verify_admin_password(pwd)):
        return True
    token = request.headers.get('X-Admin-Token', '')
    if token and asyncio.run(db.validate_admin_session(token)):
        return True
    return False


@app.route('/api/admin/bot-broadcast', methods=['POST'])
def admin_bot_broadcast():
    """Send broadcast message to all bot users via Telegram"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح - الرجاء تسجيل الدخول"}), 401
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    token = (data.get('token') or BOT_TOKEN).strip()

    if not message:
        return jsonify({"success": False, "message": "الرجاء إدخال نص الرسالة"}), 400
    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        visitors = asyncio.run(db.get_all_visitors(limit=2000))
        if not visitors:
            return jsonify({"success": False, "message": "لا يوجد مستخدمين لإرسال الرسالة"})

        success = 0
        failed = 0
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        for v in visitors:
            uid = v.get('user_id')
            if not uid:
                continue
            try:
                resp = http_requests.post(url, json={
                    "chat_id": int(uid),
                    "text": f"📢 {message}",
                    "parse_mode": "HTML"
                }, timeout=10)
                if resp.status_code == 200:
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return jsonify({
            "success": True,
            "message": f"تم الإرسال: {success} ناجح, {failed} فشل من أصل {len(visitors)}"
        })
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@app.route('/api/admin/bot-set-webhook', methods=['POST'])
def admin_bot_set_webhook():
    """Set Telegram bot webhook URL"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح - يرجى تسجيل الدخول من صفحة تسجيل الدخول"}), 401
    data = request.get_json(silent=True) or {}
    webhook_url = (data.get('url') or '').strip()
    token = (data.get('token') or BOT_TOKEN).strip()

    if not webhook_url:
        return jsonify({"success": False, "message": "الرجاء إدخال رابط Webhook"}), 400
    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/setWebhook"
        resp = http_requests.post(url, json={"url": webhook_url}, timeout=15)
        result = resp.json()
        if result.get('ok'):
            return jsonify({"success": True, "message": f"✅ تم تعيين Webhook:\n{webhook_url}"})
        return jsonify({"success": False, "message": result.get('description', 'فشل التعيين')})
    except Exception as e:
        logger.error(f"Set webhook error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@app.route('/api/admin/bot-info', methods=['POST'])
def admin_bot_info():
    """Get Telegram bot information"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح - يرجى تسجيل الدخول من صفحة تسجيل الدخول"}), 401
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or BOT_TOKEN).strip()

    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        resp = http_requests.get(url, timeout=10)
        result = resp.json()
        if not result.get('ok'):
            return jsonify({"success": False, "message": result.get('description', 'فشل الاتصال')})

        bot_data = result.get('result', {})
        stats = asyncio.run(db.get_admin_stats())

        return jsonify({
            "success": True,
            "name": bot_data.get('first_name', ''),
            "username": bot_data.get('username', ''),
            "running": True,
            "users_count": stats.get('total_users', 0),
            "downloads_today": stats.get('downloads_today', 0),
            "total_downloads": stats.get('total_downloads', 0)
        })
    except Exception as e:
        logger.error(f"Bot info error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@app.route('/api/admin/bot-webhook-info', methods=['POST'])
def admin_bot_webhook_info():
    """Get current webhook status"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or BOT_TOKEN).strip()

    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        resp = http_requests.get(url, timeout=10)
        result = resp.json()
        if not result.get('ok'):
            return jsonify({"success": False, "message": result.get('description', 'فشل')})

        wh = result.get('result', {})
        return jsonify({
            "success": True,
            "url": wh.get('url', ''),
            "has_custom_certificate": wh.get('has_custom_certificate', False),
            "pending_update_count": wh.get('pending_update_count', 0),
            "last_error_date": wh.get('last_error_date', 0),
            "last_error_message": wh.get('last_error_message', ''),
            "max_connections": wh.get('max_connections', 0),
        })
    except Exception as e:
        logger.error(f"Webhook info error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@app.route('/api/admin/bot-delete-webhook', methods=['POST'])
def admin_bot_delete_webhook():
    """Delete/remove current webhook"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or BOT_TOKEN).strip()

    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook"
        resp = http_requests.post(url, timeout=10)
        result = resp.json()
        if result.get('ok'):
            return jsonify({"success": True, "message": "✅ تم حذف Webhook بنجاح - البوت سيعمل بوضع Polling"})
        return jsonify({"success": False, "message": result.get('description', 'فشل الحذف')})
    except Exception as e:
        logger.error(f"Delete webhook error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


@app.route('/api/admin/bot-settings', methods=['POST'])
def admin_bot_settings():
    """Get all bot settings from WordPress for sync"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401

    wp_keys = [
        'tk_bot_token', 'tk_bot_enabled', 'tk_bot_webhook_url', 'tk_bot_admin_ids',
        'tk_bot_admin_name', 'tk_bot_admin_bio',
        'tk_bot_start_message', 'tk_bot_help_message', 'tk_bot_ads_message',
        'tk_bot_ads_interval', 'tk_bot_force_channels', 'tk_bot_free_downloads',
        'tk_bot_max_file_size', 'tk_bot_watermark', 'tk_bot_welcome_image',
        'tk_bot_supported_platforms'
    ]

    settings = {}
    for key in wp_keys:
        settings[key] = get_wp_option(key, '')

    return jsonify({"success": True, "settings": settings, "synced_at": datetime.now().isoformat()})


@app.route('/api/admin/bot-users', methods=['POST'])
def admin_bot_users():
    """Get list of bot users with search, filter and stats - enhanced"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    limit = int(data.get('limit', 100))
    page = int(data.get('page', 1))
    search = (data.get('search') or '').strip().lower()
    filter_country = (data.get('country') or '').strip()

    try:
        all_visitors = asyncio.run(db.get_all_visitors(limit=2000))
        stats = asyncio.run(db.get_admin_stats())

        banned_file = os.path.join(BASE_DIR, 'banned_users.txt')
        banned = set()
        if os.path.exists(banned_file):
            with open(banned_file) as f:
                banned = set(int(x) for x in f.read().strip().split('\n') if x.strip())

        filtered = []
        for v in all_visitors:
            uid = v.get('user_id', 0)
            v['is_banned'] = uid in banned
            name = (v.get('first_name', '') + ' ' + (v.get('last_name', '') or '')).lower()
            uname = (v.get('username', '') or '').lower()
            sid = str(uid)
            
            if search and not (search in name or search in uname or search in sid):
                continue
            if filter_country and v.get('country', '') != filter_country:
                continue
            
            v['language_code'] = v.get('language_code', '')
            filtered.append(v)

        total = len(filtered)
        start = (page - 1) * limit
        page_users = filtered[start:start + limit]

        countries = list(set(v.get('country', 'غير معروف') for v in all_visitors if v.get('country')))

        return jsonify({
            "success": True,
            "users": page_users,
            "total": total,
            "pages": max(1, (total + limit - 1) // limit) if total else 0,
            "page": page,
            "total_all": stats.get('total_users', 0),
            "monthly": stats.get('monthly_users', 0),
            "banned_count": len(banned),
            "countries": sorted(countries)
        })
    except Exception as e:
        logger.error(f"Bot users error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-users-export', methods=['POST'])
def admin_bot_users_export():
    """Export bot users as CSV"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    try:
        visitors = asyncio.run(db.get_all_visitors(limit=5000))
        import csv, io
        output = io.StringIO()
        w = csv.writer(output)
        w.writerow(['user_id','first_name','last_name','username','country','language','visit_count','first_visit','last_visit','is_premium'])
        for v in visitors:
            w.writerow([
                v.get('user_id',''), v.get('first_name',''), v.get('last_name',''),
                v.get('username',''), v.get('country',''), v.get('language_code',''),
                v.get('visit_count',''), v.get('first_visit',''), v.get('last_visit',''),
                v.get('is_premium', 0)
            ])
        from flask import Response
        return Response(output.getvalue(), mimetype="text/csv",
                       headers={"Content-Disposition": "attachment;filename=bot_users.csv"})
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-user-action', methods=['POST'])
def admin_bot_user_action():
    """Enhanced user actions: ban, unban, delete, bulk_delete, bulk_ban"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    action = data.get('action', '').strip()
    target_id = int(data.get('user_id', 0))
    ids = data.get('user_ids', [])
    value = data.get('value', '').strip()

    banned_file = os.path.join(BASE_DIR, 'banned_users.txt')

    def _load_banned():
        if os.path.exists(banned_file):
            with open(banned_file) as f:
                return set(int(x) for x in f.read().strip().split('\n') if x.strip())
        return set()

    def _save_banned(b):
        with open(banned_file, 'w') as f:
            f.write('\n'.join(str(x) for x in b) if b else '')

    try:
        if action == 'bulk_ban' and ids:
            banned = _load_banned()
            banned.update(int(i) for i in ids)
            _save_banned(banned)
            return jsonify({"success": True, "message": f"تم حظر {len(ids)} مستخدم"})

        elif action == 'bulk_delete' and ids:
            deleted = 0
            for uid in ids:
                ok = asyncio.run(db.delete_visitor(int(uid)))
                if ok: deleted += 1
            return jsonify({"success": True, "message": f"تم حذف {deleted} مستخدم"})

        if not target_id:
            return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

        if action == 'ban':
            banned = _load_banned()
            banned.add(target_id)
            _save_banned(banned)
            return jsonify({"success": True, "message": f"تم حظر المستخدم {target_id}"})

        elif action == 'unban':
            banned = _load_banned()
            banned.discard(target_id)
            _save_banned(banned)
            return jsonify({"success": True, "message": f"تم إلغاء حظر المستخدم {target_id}"})

        elif action == 'delete_user':
            ok = asyncio.run(db.delete_visitor(target_id))
            return jsonify({"success": ok, "message": "تم حذف المستخدم" if ok else "فشل الحذف"})

        elif action == 'set_points':
            points = int(data.get('value', 0))
            asyncio.run(db.update_user(target_id, points=points))
            return jsonify({"success": True, "message": f"تم تحديث النقاط للمستخدم {target_id}"})

        elif action == 'set_tier':
            tier = value
            asyncio.run(db.update_user(target_id, tier=tier))
            return jsonify({"success": True, "message": f"تم تغيير مستوى المستخدم {target_id} إلى {tier}"})

        elif action == 'bulk_set_tier' and ids:
            tier = value
            updated = 0
            for uid in ids:
                ok = asyncio.run(db.update_user(int(uid), tier=tier))
                if ok: updated += 1
            return jsonify({"success": True, "message": f"تم تغيير مستوى {updated} مستخدم"})

        else:
            return jsonify({"success": False, "message": f"إجراء غير معروف: {action}"}), 400

    except Exception as e:
        logger.error(f"User action error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-user-detail', methods=['POST'])
def admin_bot_user_detail():
    """Get details for a single bot user"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

    try:
        user = asyncio.run(db.get_visitor(user_id))
        downloads = asyncio.run(db.get_user_downloads(user_id, limit=50))
        points = asyncio.run(db.get_user_points(user_id))
        banned_file = os.path.join(BASE_DIR, 'banned_users.txt')
        banned = set()
        if os.path.exists(banned_file):
            with open(banned_file) as f:
                banned = set(int(x) for x in f.read().strip().split('\n') if x.strip())

        return jsonify({
            "success": True,
            "user": user,
            "downloads": downloads,
            "points": points or 0,
            "is_banned": user_id in banned
        })
    except Exception as e:
        logger.error(f"User detail error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-user-activity', methods=['POST'])
def admin_bot_user_activity():
    """Get activity log for a single user"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

    try:
        downloads = asyncio.run(db.get_user_downloads(user_id, limit=100))
        daily = asyncio.run(db.get_daily_download_count(user_id))
        today_limit = asyncio.run(db.get_daily_limit(user_id))
        return jsonify({
            "success": True,
            "downloads": downloads,
            "daily_count": daily,
            "daily_limit": today_limit.get('daily_limit', 0) if today_limit else 0
        })
    except Exception as e:
        logger.error(f"User activity error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/send-message', methods=['POST'])
def admin_send_message():
    """Send a direct message to a single user via Telegram"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id', '')
    message = (data.get('message') or '').strip()
    token = (data.get('token') or BOT_TOKEN).strip()

    if not user_id or not message:
        return jsonify({"success": False, "message": "معرف المستخدم والرسالة مطلوبان"}), 400
    if not token:
        return jsonify({"success": False, "message": "لم يتم تعيين توكن البوت"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = http_requests.post(url, json={
            "chat_id": int(user_id),
            "text": f"📩 {message}",
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code == 200:
            return jsonify({"success": True, "message": "تم إرسال الرسالة"})
        return jsonify({"success": False, "message": "فشل إرسال الرسالة"}), 500
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/promote-user', methods=['POST'])
def admin_promote_user():
    """Promote a user to the next tier"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    user_id = int(data.get('user_id', 0))
    tier_map = {'free': 'premium', 'premium': 'vip', 'vip': 'pro', 'pro': 'pro'}
    if not user_id:
        return jsonify({"success": False, "message": "معرف المستخدم مطلوب"}), 400

    try:
        user = asyncio.run(db.get_user(user_id))
        current_tier = user.get('tier', 'free') if user else 'free'
        new_tier = tier_map.get(current_tier, 'premium')
        asyncio.run(db.update_user(user_id, tier=new_tier))
        return jsonify({"success": True, "message": f"تمت ترقية المستخدم إلى {new_tier}"})
    except Exception as e:
        logger.error(f"Promote user error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-subscribers', methods=['POST'])
def admin_bot_subscribers():
    """Get all subscribers with enhanced data including keys"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    status_filter = (data.get('status') or '').strip()
    search = (data.get('search') or '').strip().lower()
    
    try:
        new_requests = asyncio.run(db.get_subscription_requests("new"))
        active_requests = asyncio.run(db.get_subscription_requests("active"))
        
        subscribers = []
        for r in new_requests:
            r['status_label'] = 'قيد المراجعة'
            r['status_class'] = 'pending'
            r['keys'] = []
            email = r.get('email', '')
            if email:
                keys = asyncio.run(db.find_keys_by_owner(email))
                r['keys'] = keys if keys else []
            subscribers.append(r)
        for r in active_requests:
            r['status_label'] = 'مفعل'
            r['status_class'] = 'active'
            r['keys'] = []
            email = r.get('email', '')
            if email:
                keys = asyncio.run(db.find_keys_by_owner(email))
                r['keys'] = keys if keys else []
            subscribers.append(r)

        if search:
            subscribers = [s for s in subscribers if 
                search in (s.get('name','')+s.get('email','')).lower()]

        pending = sum(1 for s in subscribers if s.get('status') == 'new')
        active = sum(1 for s in subscribers if s.get('status') == 'active')

        return jsonify({
            "success": True,
            "subscribers": subscribers,
            "pending": pending,
            "active": active,
            "total": len(subscribers)
        })
    except Exception as e:
        logger.error(f"Subscribers error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-subscriber-lookup', methods=['POST'])
def admin_bot_subscriber_lookup():
    """Look up a subscriber by email with full details"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    
    if not email or '@' not in email:
        return jsonify({"success": False, "message": "بريد غير صحيح"}), 400

    try:
        keys = asyncio.run(db.find_keys_by_owner(email))
        
        sub_info = None
        for status in ['new', 'active', 'dismissed']:
            subs = asyncio.run(db.get_subscription_requests(status))
            for s in subs:
                if s.get('email') == email:
                    sub_info = s
                    break
            if sub_info:
                break
        
        total_usage = sum(int(k.get('usage_count', 0)) for k in keys) if keys else 0
        total_limit = sum(int(k.get('usage_limit', 0)) for k in keys) if keys else 0
        
        return jsonify({
            "success": True,
            "found": bool(sub_info or keys),
            "email": email,
            "subscription": sub_info,
            "keys": keys,
            "keys_count": len(keys) if keys else 0,
            "total_usage": total_usage,
            "total_limit": total_limit,
        })
    except Exception as e:
        logger.error(f"Subscriber lookup error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-subscriber-action', methods=['POST'])
def admin_bot_subscriber_action():
    """Actions on subscribers: activate, dismiss, update_limit, add_note"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip()
    sub_id = int(data.get('id', 0))
    email = (data.get('email') or '').strip().lower()
    limit = int(data.get('limit', 50))
    platform = (data.get('platform') or 'TikTok').strip()
    note = (data.get('note') or '').strip()

    if not action:
        return jsonify({"success": False, "message": "بيانات غير مكتملة"}), 400

    try:
        if action == 'activate':
            import secrets
            KEY_PREFIXES = {"TikTok": "ttk-"}
            prefix = KEY_PREFIXES.get(platform, "k-")
            key = prefix + secrets.token_hex(4)
            ok = asyncio.run(db.create_activation_key(key=key, owner_name=email, usage_limit=limit, notes="اشتراك مفعل عبر لوحة البوت", platform=platform))
            if ok:
                asyncio.run(db.update_subscription_status(sub_id, "active"))
                return jsonify({"success": True, "message": f"تم تفعيل الاشتراك", "key": key})

        elif action == 'dismiss':
            asyncio.run(db.update_subscription_status(sub_id, "dismissed"))
            return jsonify({"success": True, "message": "تم رفض الطلب"})

        elif action == 'update_limit' and email:
            keys = asyncio.run(db.find_keys_by_owner(email))
            updated = 0
            for k in keys:
                ok = asyncio.run(db.update_activation_key(k['key'], usage_limit=limit))
                if ok: updated += 1
            return jsonify({"success": True, "message": f"تم تحديث {updated} مفتاح", "updated": updated})

        elif action == 'create_key':
            import secrets
            KEY_PREFIXES = {"TikTok": "ttk-"}
            prefix = KEY_PREFIXES.get(platform, "k-")
            key = prefix + secrets.token_hex(4)
            ok = asyncio.run(db.create_activation_key(key=key, owner_name=email, usage_limit=limit, notes=note or "مفتاح يدوي", platform=platform))
            if ok:
                return jsonify({"success": True, "message": f"تم إنشاء مفتاح للمشترك", "key": key})
            return jsonify({"success": False, "message": "فشل إنشاء المفتاح"}), 500

        elif action == 'delete_key':
            key_val = (data.get('key') or '').strip()
            if key_val:
                ok = asyncio.run(db.delete_activation_key(key_val))
                return jsonify({"success": ok, "message": "تم حذف المفتاح" if ok else "فشل الحذف"})

        else:
            return jsonify({"success": False, "message": f"إجراء غير معروف: {action}"}), 400

    except Exception as e:
        logger.error(f"Subscriber action error: {e}")
        return jsonify({"success": False, "message": str(e)[:100]}), 500


@app.route('/api/admin/bot-restart', methods=['POST'])
def admin_bot_restart():
    """Restart the Telegram bot service"""
    if not _require_bot_admin():
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    try:
        import subprocess
        result = subprocess.run(['sudo', 'systemctl', 'restart', 'download-bot.service'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("Bot service restarted via admin panel")
            return jsonify({"success": True, "message": "✅ تم إعادة تشغيل البوت بنجاح"})
        return jsonify({"success": False, "message": f"فشل: {result.stderr[:100]}"}), 500
    except Exception as e:
        logger.error(f"Bot restart error: {e}")
        return jsonify({"success": False, "message": f"خطأ: {str(e)[:100]}"}), 500


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
