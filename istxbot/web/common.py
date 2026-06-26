"""
الحالة والمساعدات المشتركة لتطبيق الويب — تستوردها blueprints و app.py
"""
import os
import sys
import asyncio
import logging
from pathlib import Path


import requests as http_requests
from flask import request, g

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.downloaders.tiktok_downloader import TikTokDownloader
from bot.utils.database import DatabaseManager, init_database
from config.settings import settings

logger = logging.getLogger("web_app")

# ═══ Paths & Config ═══

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(APP_DIR)

DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "bot_data.db"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", os.path.join(BASE_DIR, "downloads"))).resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

db = DatabaseManager(DB_PATH)
MAX_DAILY_DOWNLOADS_PER_KEY = 100
_db_initialized = False

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")
ADMIN_PATH = os.getenv("ADMIN_PATH", "control")

# ═══ Platform Configs ═══

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

# ═══ Downloader Instances ═══

_downloaders = {
    "TikTok": TikTokDownloader(),
}
for d in _downloaders.values():
    d.download_dir = DOWNLOAD_DIR

_SUBDOMAIN_MAP = {
    "tiktok": "TikTok",
}

DEFAULT_PLATFORM = "TikTok"

# ═══ Email OTP Store ═══

_email_otp = {}

# ═══ Helper Functions ═══

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
    """Get platform config merged with DB overrides"""
    platform = g.get("platform", DEFAULT_PLATFORM)
    default_config = _PLATFORM_CONFIGS.get(platform, _PLATFORM_CONFIGS[DEFAULT_PLATFORM])
    config = {**_DEFAULT_SITE_SETTINGS, **default_config}
    try:
        all_settings = asyncio.run(db.get_all_site_settings())
    except Exception:
        all_settings = {}
    for k, v in all_settings.items():
        if v and not k.startswith('TikTok:'):
            config[k] = v
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


def _get_ads_settings() -> dict:
    """Get ads settings from database"""
    try:
        all_settings = asyncio.run(db.get_all_site_settings())
        ads = {}
        slots = ["top", "native", "middle", "after_steps", "bottom", "sticky_bottom"]
        for slot in slots:
            html = all_settings.get(f"ads:{slot}_html", "")
            enabled = all_settings.get(f"ads:{slot}_enabled", "true")
            ads[f"{slot}_html"] = html if str(enabled).lower() in ("true", "1", "yes", "on") else ""
            ads[f"{slot}_enabled"] = str(enabled).lower() in ("true", "1", "yes", "on")
        return ads
    except Exception:
        return {}


def inject_site_settings():
    """Context processor for templates"""
    return {
        "site_settings": _get_platform_config(),
        "platform": g.get("platform", DEFAULT_PLATFORM),
        "ads_settings": _get_ads_settings()
    }


def _ensure_db():
    """Lazy-init database on first request"""
    global _db_initialized
    if not _db_initialized:
        asyncio.run(_init_db())
        _db_initialized = True


async def _init_db():
    await db.initialize()
    logger.info("Web app database initialized")


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

        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            device_type = 'mobile'
        elif 'tablet' in ua_lower or 'ipad' in ua_lower:
            device_type = 'tablet'
        else:
            device_type = 'desktop'

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

        country = request.headers.get('CF-IPCountry', 'unknown')
        country_code = country if country != 'unknown' else '??'

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


def send_email_otp(email: str, otp: str) -> bool:
    """Send OTP code via email using SMTP"""
    return _send_email(email, 'رمز استرجاع المفتاح - istx.io',
        f"""<html dir="rtl"><body style="font-family:Arial,sans-serif;background:#0f0f0f;color:#e0e0e0;padding:20px">
<div style="max-width:400px;margin:0 auto;background:#1a1a2e;border-radius:12px;padding:24px;text-align:center">
<h2 style="color:#fe2c55">🔐 استرجاع المفتاح</h2>
<p style="color:#888">رمز التحقق الخاص بك هو:</p>
<div style="font-size:32px;font-weight:800;color:#fff;letter-spacing:8px;margin:16px 0">{otp}</div>
<p style="color:#666;font-size:12px">ينتهي الرمز بعد 5 دقائق</p>
<p style="color:#555;font-size:11px;margin-top:24px">إذا لم تطلب هذا الرمز، تجاهل هذه الرسالة</p>
</div></body></html>""")


def send_subscription_email(email: str, subject: str, body_html: str) -> bool:
    """Send a subscription-related email to the user"""
    return _send_email(email, subject, body_html)


def _send_email(email: str, subject: str, body_html: str) -> bool:
    """Generic email sender via SMTP"""
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
        logger.info(f"Email sent to {email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def _require_admin():
    """Check admin authentication via session token or password"""
    data = request.get_json(silent=True) or {}
    pwd = (data.get('password') or '').strip()
    if pwd:
        import hashlib
        pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
        expected = os.getenv('ADMIN_PASSWORD_HASH', '')
        if expected and pwd_hash == expected:
            return True

    token = request.headers.get('X-Admin-Token', '')
    if token:
        session = asyncio.run(db.verify_session(token))
        if session.get('valid'):
            return True
    token_json = (data.get('token') or '').strip()
    if token_json:
        session = asyncio.run(db.verify_session(token_json))
        if session.get('valid'):
            return True
    return False


def _require_bot_admin():
    """Check admin auth - supports API key, password, or admin session token"""
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


def get_wp_option(key, default=None):
    """Get an option from WordPress database"""
    try:
        wp_db_path = os.getenv("WP_DB_PATH", "")
        if not wp_db_path:
            return default
        import sqlite3
        conn = sqlite3.connect(wp_db_path)
        cur = conn.cursor()
        cur.execute("SELECT option_value FROM wp_options WHERE option_name = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
        return default
    except Exception:
        return default


def get_daily_download_limit():
    """Global daily download limit from WordPress or env"""
    limit = get_wp_option('tk_bot_free_downloads', os.getenv("DAILY_DOWNLOAD_LIMIT", "5"))
    try:
        return int(limit)
    except (ValueError, TypeError):
        return 5


def get_reset_hour():
    """When downloads reset (UTC hour)"""
    try:
        return int(os.getenv("RESET_HOUR", "0"))
    except (ValueError, TypeError):
        return 0


