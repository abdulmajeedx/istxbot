from aiogram import Router, F, types
from aiogram.types import Message
from aiogram.enums import ParseMode
import logging
import asyncio
import os
import time
from typing import Optional
from datetime import datetime as dt
from collections import defaultdict
from collections import defaultdict

from bot.utils.database import DatabaseManager

from bot.downloaders.tiktok_downloader import TikTokDownloader
from config.settings import settings, get_wp_option
import os as _os_module

# Try to import improved TikTok downloader
ImprovedTikTokDownloader = None
try:
    from bot.downloaders.tiktok_improved_downloader import ImprovedTikTokDownloader
    IMPROVED_TIKTOK_ENABLED = True
except ImportError:
    IMPROVED_TIKTOK_ENABLED = False

TikTokAPIDownloader = None
try:
    from bot.downloaders.tiktok_api_downloader import TikTokAPIDownloader
    TIKTOK_API_DOWNLOADER = True
except ImportError:
    TIKTOK_API_DOWNLOADER = False
from bot.utils.helpers import (
    get_platform_from_url,
    cleanup_downloads,
    get_file_size_mb,
    is_video_file,
    is_audio_file,
    is_image_file,
    sanitize_filename,
    format_bytes,
)
from bot.utils.security import validate_url, InvalidURLError, XSSDetectedError, CRLFInjectionError

from bot.utils.rate_limiter import get_rate_limiter, RateLimitMiddleware
from bot.utils.exceptions import (
    DownloadError, ValidationError,
    StructuredLogger, ErrorContext, get_dead_letter_queue
)
from bot.utils.database import get_db_manager

try:
    from bot.utils.priority_queue import get_queue_manager, UserTier as PQUserTier
    PRIORITY_QUEUE_ENABLED = True
    UserTier = PQUserTier
except ImportError:
    PRIORITY_QUEUE_ENABLED = False
    UserTier = None

router = Router()

# ─── Anti-Spam / Flood Control ───
_flood_tracker = defaultdict(list)
_FLOOD_WINDOW = 10  # seconds
_FLOOD_MAX_MSGS = 5  # max messages in window
_BAN_THRESHOLD = 3  # flood strikes before temp ban
_flood_strikes = defaultdict(int)

async def check_flood(user_id: int) -> tuple:
    """Returns (allowed, warning_msg). Tracks message frequency per user."""
    now = time.time()
    times = _flood_tracker[user_id]
    times = [t for t in times if now - t < _FLOOD_WINDOW]
    _flood_tracker[user_id] = times + [now]
    
    if len(times) >= _FLOOD_MAX_MSGS:
        _flood_strikes[user_id] += 1
        if _flood_strikes[user_id] >= _BAN_THRESHOLD:
            try:
                db = DatabaseManager(os.getenv("DB_PATH", "bot_data.db"))
                await db.ban_user(user_id)
                logger.warning(f"User {user_id} auto-banned for flood")
            except:
                pass
            return False, "🚫 تم حظرك تلقائياً لكثرة الطلبات. تواصل مع الأدمن."
        return False, "⚠️ طلبات كثيرة جداً. انتظر قليلاً..."
    return True, None

# ─── Channel Join Tracking ───
_channel_prompts = defaultdict(int)
_channel_joins = defaultdict(int)

def track_channel_prompt(user_id: int):
    _channel_prompts[user_id] += 1

def track_channel_join(user_id: int):
    _channel_joins[user_id] += 1

def get_channel_stats():
    return {
        'prompts': sum(_channel_prompts.values()),
        'joins': sum(_channel_joins.values()),
        'prompt_users': len(_channel_prompts),
        'join_users': len(_channel_joins),
    }

# ─── Telegram Admin Notifications ───
_last_notify_time = defaultdict(float)

async def notify_admin(text: str, min_interval: int = 60):
    """Send notification to admin via Telegram, rate-limited"""
    now = time.time()
    key = hash(text[:50])
    if now - _last_notify_time[key] < min_interval:
        return
    _last_notify_time[key] = now
    
    admin_ids_str = get_wp_option('tk_bot_admin_ids', '8597976445')
    try:
        admin_ids = [int(x.strip()) for x in admin_ids_str.split('\n') if x.strip()]
    except:
        admin_ids = [8597976445]
    
    import aiohttp
    for aid in admin_ids[:3]:
        try:
            async with aiohttp.ClientSession() as s:
                url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
                await s.post(url, json={"chat_id": aid, "text": text[:4000], "parse_mode": "HTML"}, timeout=aiohttp.ClientTimeout(total=5))
        except Exception as e:
                logger.debug(f"Notify admin {aid} failed: {e}")

logger = logging.getLogger(__name__)
structured_logger = StructuredLogger("main_handlers", get_dead_letter_queue())
rate_limiter = get_rate_limiter()
rate_middleware = RateLimitMiddleware(rate_limiter, settings.ADMIN_ID)
db_manager = get_db_manager()


def format_styled_message(title: str, sections: list[tuple[str, str]], footer: str | None = None) -> str:
    divider = "\n".join(['━' * 18, ''])
    parts = [f"✨ *{title}* ✨", divider]
    for sec_title, sec_body in sections:
        parts.append(f"• *{sec_title}*\n{sec_body}\n")
    if footer:
        parts.append(divider)
        parts.append(footer)
    return "\n".join(parts)

LANGUAGE_TO_COUNTRY = {
    'ar': 'السعودية',
    'en': 'USA',
    'fr': 'France',
    'de': 'Germany',
    'es': 'Spain',
    'it': 'Italy',
    'pt': 'Portugal',
    'ru': 'Russia',
    'tr': 'Turkey',
    'fa': 'Iran',
    'ur': 'Pakistan',
    'hi': 'India',
    'zh': 'China',
    'ja': 'Japan',
    'ko': 'Korea',
    'vi': 'Vietnam',
    'th': 'Thailand',
    'id': 'Indonesia',
    'ms': 'Malaysia',
    'bn': 'Bangladesh',
    'nl': 'Netherlands',
    'pl': 'Poland',
    'uk': 'Ukraine',
    'sv': 'Sweden',
    'no': 'Norway',
    'da': 'Denmark',
    'fi': 'Finland',
    'cs': 'Czech Republic',
    'ro': 'Romania',
    'hu': 'Hungary',
    'el': 'Greece',
    'bg': 'Bulgaria',
    'sk': 'Slovakia',
    'hr': 'Croatia',
    'sr': 'Serbia',
    'sl': 'Slovenia',
    'et': 'Estonia',
    'lv': 'Latvia',
    'lt': 'Lithuania',
    'mk': 'North Macedonia',
    'sq': 'Albania',
    'mt': 'Malta',
    'cy': 'Cyprus',
    'he': 'Israel',
    'ps': 'Palestine',
    'kk': 'Kazakhstan',
    'uz': 'Uzbekistan',
    'ky': 'Kyrgyzstan',
    'tg': 'Tajikistan',
    'tk': 'Turkmenistan',
    'az': 'Azerbaijan',
    'ka': 'Georgia',
    'hy': 'Armenia',
    'be': 'Belarus',
    'my': 'Myanmar',
    'km': 'Cambodia',
    'lo': 'Laos',
    'mn': 'Mongolia',
    'ne': 'Nepal',
    'si': 'Sri Lanka',
    'ml': 'Kerala (India)',
    'ta': 'Tamil Nadu (India)',
    'te': 'Andhra Pradesh (India)',
    'kn': 'Karnataka (India)',
    'gu': 'Gujarat (India)',
    'pa': 'Punjab (India)',
    'or': 'Odisha (India)',
    'as': 'Assam (India)',
    'mr': 'Maharashtra (India)',
    'sd': 'Sindh (Pakistan)',
}

tiktok_dl = TikTokDownloader()

# Use TikTok Yt-DLP Downloader (most reliable)
tiktok_dl = TikTokDownloader()
logger.info("✓ Using TikTok Yt-DLP Downloader")

SUPPORTED_PLATFORMS = {
    'TikTok': tiktok_dl,
}

BANNED_USERS_FILE = "banned_users.txt"

def _load_banned() -> set:
    """تحميل قائمة المحظورين من الملف"""
    try:
        if _os_module.path.exists(BANNED_USERS_FILE):
            with open(BANNED_USERS_FILE) as f:
                content = f.read().strip()
                if content:
                    return set(int(x) for x in content.split('\n') if x.strip())
    except:
        pass
    return set()

def is_user_banned(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم محظوراً"""
    return user_id in _load_banned()

async def check_banned_and_alert(message: Message) -> bool:
    """التحقق من حظر المستخدم وعرض إشعار له"""
    user_id = message.from_user.id if message.from_user else 0
    if not user_id:
        return False
    if is_user_banned(user_id):
        await message.answer(
            "🚫 *تم حظرك من استخدام البوت*\n\n"
            "لقد تم تقييد وصولك إلى خدمات البوت من قبل الإدارة.\n"
            "للتواصل مع الدعم: @" + get_wp_option('tk_telegram_username', 'qazvvx'),
            parse_mode="Markdown"
        )
        return True
    return False

def _get_supported_platforms():
    """Get supported platforms from WordPress live"""
    wp_platforms = get_wp_option('tk_bot_supported_platforms', 'TikTok')
    return [p.strip() for p in wp_platforms.split(',') if p.strip()]

def _get_daily_limit():
    return 100

def _get_max_file_size_mb():
    """Get max file size from WordPress live"""
    val = get_wp_option('tk_bot_max_file_size', '50')
    try:
        return int(val)
    except:
        return 50

async def record_visitor(message: Message, activity_type: str = 'message'):
    """Record visitor information to database and track session"""
    try:
        if not message or not message.from_user:
            return
        
        user = message.from_user
        language_code = user.language_code or 'en'
        country = LANGUAGE_TO_COUNTRY.get(language_code, 'Unknown')
        
        visitor_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'language_code': language_code,
            'country': country,
            'is_bot': 1 if user.is_bot else 0,
            'is_premium': 1 if hasattr(user, 'is_premium') and user.is_premium else 0,
            'added_to_attachment_menu': 1 if hasattr(user, 'added_to_attachment_menu') and user.added_to_attachment_menu else 0
        }
        
        await db_manager.record_visitor(visitor_data)
        
        # Track real-time session
        await db_manager.track_user_session(visitor_data, activity_type)
        
        # Update user activity timestamp
        await db_manager.update_user_activity(user.id)
        
        logger.debug(f"Visitor tracked: {user.id} ({user.username}) - {activity_type}")
    except Exception as e:
        logger.error(f"Error recording visitor: {e}")

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    if await check_banned_and_alert(message):
        return
    await record_visitor(message, 'start_command')
    
    target_lang = 'ar'
    if message.from_user and hasattr(message.from_user, 'language_code'):
        target_lang = message.from_user.language_code or 'ar'
    
    wp_msg = get_wp_option('tk_bot_start_message', '')
    admin_name = get_wp_option('tk_bot_admin_name', '')
    admin_username = get_wp_option('tk_telegram_username', 'qazvvx')
    
    if wp_msg and target_lang == 'ar':
        welcome_msg = wp_msg
    elif target_lang == 'ar':
        welcome_msg = format_styled_message(
            "بوت التحميل الشامل",
            [
                ("منصات الدعم", "TikTok"),
                ("كيف يعمل؟", "أرسل رابط الفيديو وسيتم التحميل مباشرة بجودة عالية."),
                ("أوامر مفيدة", "`/help` جميع الميزات"),
                ("الدعم", f"للاستفسار والدعم: @{admin_username}")
            ]
        )
    else:
        welcome_msg = (
            "Welcome to TikTok Video Downloader Bot!\n\n"
            "Supported Platform:\n"
            "TikTok\n\n"
            "How to use:\n"
            "1) Copy the video link\n"
            "2) Send it here\n"
            "3) Wait for download\n"
            "4) Receive the file!\n\n"
            "Commands:\n"
            f"/help - Full guide\n\n"
            f"Support: @{admin_username}"
        )
    
    await message.answer(welcome_msg)

@router.message(F.text.startswith("/help"))
async def cmd_help(message: Message):
    if await check_banned_and_alert(message):
        return
    await record_visitor(message, 'help_command')
    user_id = message.from_user.id if message.from_user else 0
    is_admin = settings.is_admin(user_id)
    
    target_lang = 'ar'
    if message.from_user and hasattr(message.from_user, 'language_code'):
        target_lang = message.from_user.language_code or 'ar'
    
    if is_admin:
        admin_help = (
            "🔧 *أوامر الأدمن*\n\n"
            "• /admin - جميع أوامر الأدمن\n"
            "• /stats - إحصائيات البوت\n"
            "• /broadcast - رسالة للجميع\n"
            "• /ban ID - حظر مستخدم\n"
            "• /unban ID - فك حظر\n\n"
            "⚙️ للإعدادات: لوحة التحكم\n"
            "inspiredownloader.com/wp-admin/"
        )
        
        await message.answer(admin_help)
    else:
        wp_help = get_wp_option('tk_bot_help_message', '')
        admin_username = get_wp_option('tk_telegram_username', 'qazvvx')
        
        if wp_help and target_lang == 'ar':
            await message.answer(wp_help)
        else:
            user_help = format_styled_message(
                "دليل الاستخدام",
                [
                    ("الخطوات", "1) انسخ الرابط\n2) أرسله هنا\n3) انتظر التحميل\n4) استلم الملف فوراً"),
                    ("Supported Platforms", "TikTok"),
                    ("مزايا", "إزالة العلامة المائية، جودة عالية"),
                    ("أوامر", "`/help` للمزيد")
                ],
                footer=f"للاستفسار والدعم: @{admin_username}"
            )
            await message.answer(user_help, parse_mode=ParseMode.MARKDOWN)

async def _check_force_channels(user_id: int, bot_token: str) -> list:
    """Check which force channels the user hasn't joined yet"""
    channels_str = get_wp_option('tk_bot_force_channels', '')
    if not channels_str or not channels_str.strip():
        return []
    
    channels = [c.strip() for c in channels_str.split('\n') if c.strip()]
    if not channels:
        return []
    
    not_joined = []
    import aiohttp
    async with aiohttp.ClientSession() as session:
        for channel in channels:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
                params = {"chat_id": channel, "user_id": user_id}
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    if data.get('ok'):
                        status = data.get('result', {}).get('status', '')
                        if status in ('left', 'kicked', None, ''):
                            not_joined.append(channel)
                    else:
                        not_joined.append(channel)
            except Exception as e:
                logger.debug(f"Force channel check error for {channel}: {e}")
                not_joined.append(channel)
    
    return not_joined

async def _get_user_download_count(user_id: int) -> int:
    """Get today's download count for a user from priority queue or DB"""
    try:
        if PRIORITY_QUEUE_ENABLED:
            from bot.utils.priority_queue import get_queue_manager
            qm = get_queue_manager()
            if qm:
                return qm.get_user_daily_count(user_id)
    except Exception:
        pass
    return 0

async def _should_check_channels(user_id: int, bot_token: str) -> bool:
    """Returns True if user needs to join channels (after free downloads used)"""
    channels_str = get_wp_option('tk_bot_force_channels', '')
    if not channels_str or not channels_str.strip():
        return False
    
    free_downloads = int(get_wp_option('tk_bot_free_downloads', '3') or '3')
    if free_downloads <= 0:
        return True
    
    count = await _get_user_download_count(user_id)
    return count >= free_downloads

@router.message(F.text)
async def handle_text(message: Message):
    """Handle regular text messages (skip commands)."""
    if await check_banned_and_alert(message):
        return
    
    user_id = message.from_user.id if message.from_user else 0
    
    allowed, flood_msg = await check_flood(user_id)
    if not allowed:
        if flood_msg:
            await message.answer(flood_msg)
        return
    
    if user_id and not settings.is_admin(user_id):
        should_check = await _should_check_channels(user_id, settings.BOT_TOKEN)
        if should_check:
            not_joined = await _check_force_channels(user_id, settings.BOT_TOKEN)
            if not_joined:
                track_channel_prompt(user_id)
                asyncio.create_task(notify_admin(f"📢 مستخدم <code>{user_id}</code> وصل للحد المجاني ويحتاج للاشتراك في القناة"))
                free_downloads = int(get_wp_option('tk_bot_free_downloads', '3') or '3')
                lines = [f"🎯 <b>تحميلاتك المجانية ({free_downloads}) انتهت</b>\n"]
                lines.append("للمتابعة، اشترك في القناة:")
                for ch in not_joined:
                    ch_name = ch.replace('@', '')
                    lines.append(f"👉 {ch}")
                lines.append(f"\nبعد الاشتراك أرسل الرابط 🚀")
                await message.answer('\n'.join(lines), disable_web_page_preview=True)
                return
    
    await record_visitor(message)
    queue_manager = None
    if PRIORITY_QUEUE_ENABLED:
        from bot.utils.priority_queue import get_queue_manager
        queue_manager = get_queue_manager()
    
    url = None
    user_id = None
    
    try:
        if not message or not message.text:
            return
        
        if message.text.startswith('/'):
            return
        
        url = message.text.strip()
        user_id = message.from_user.id if message.from_user else 0
        
        if not url.startswith(('http://', 'https://')):
            target_lang = 'ar'
            if message.from_user and hasattr(message.from_user, 'language_code'):
                target_lang = message.from_user.language_code or 'ar'
            
            admin_username = get_wp_option('tk_telegram_username', 'qazvvx')
            welcome_msg = get_wp_option('tk_bot_start_message', '')
            
            if not welcome_msg or target_lang != 'ar':
                welcome_msg = (
                    "Welcome to TikTok Video Downloader Bot!\n\n"
                    "Supported Platform:\n"
                    "TikTok\n\n"
                    "How to use:\n"
                    "1) Copy the video link\n"
                    "2) Send it here\n"
                    "3) Wait for download\n"
                    "4) Receive the file!\n\n"
                    "Commands:\n"
                    "/help - Full guide\n\n"
                    f"Support: @{admin_username}"
                )
            
            await message.answer(welcome_msg)
            return
        
        # Rate limiting check
        allowed, error_msg = await rate_middleware.check(user_id)
        if not allowed:
            await message.answer(error_msg or "❌ تجاوزت الحد المسموح من الطلبات")
            return
        
        # URL validation
        is_valid, validation_error = validate_url(url)
        if not is_valid:
            context = ErrorContext(user_id=user_id, url=url, action="validate_url")
            structured_logger.log_warning(f"Invalid URL: {validation_error}", context=context.to_dict())
            await message.answer(f"❌ رابط غير صالح: {validation_error}")
            return
        
        platform = get_platform_from_url(url)
        
        if not platform:
            logger.warning(f"Unsupported platform for URL: {url} | User: {user_id}")
            await message.answer("❌ المنصة غير مدعومة حالياً")
            return
        
        supported = _get_supported_platforms()
        if platform not in SUPPORTED_PLATFORMS or platform not in supported:
            logger.warning(f"Platform detected but not in supported list: {platform} | URL: {url}")
            await message.answer(f"❌ منصة {platform} غير مدعومة حالياً")
            return
        
        logger.info(f"Detected platform: {platform} | URL: {url} | User: {user_id}")

        if queue_manager:
            queue_manager.register_online_user(user_id)
            queue_manager.register_monthly_user(user_id)
            if message.from_user:
                queue_manager.register_user_name(
                    user_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name
                )
        
        downloader = SUPPORTED_PLATFORMS[platform]
        
        status_message = await message.answer(get_wp_option('tk_bot_downloading_msg', f"⏳ جاري التحميل من {platform}..."))
        
        await _download_and_send(message, downloader, url, platform, status_message, user_id, queue_manager)
        
    except (InvalidURLError, XSSDetectedError, CRLFInjectionError) as e:
        ctx_user_id = user_id if user_id is not None else (message.from_user.id if message.from_user else 0)
        ctx_url = url if url is not None else ""
        context = ErrorContext(user_id=ctx_user_id, url=ctx_url)
        structured_logger.log_error(e, context=context)
        await message.answer(f"❌ رابط غير آمن: {str(e)}")
    except ValidationError as e:
        ctx_user_id = user_id if user_id is not None else (message.from_user.id if message.from_user else 0)
        ctx_url = url if url is not None else ""
        context = ErrorContext(user_id=ctx_user_id, url=ctx_url)
        structured_logger.log_error(e, context=context)
        await message.answer(f"❌ خطأ في التحقق: {str(e)}")
    except Exception as e:
        ctx_user_id = user_id if user_id is not None else (message.from_user.id if message.from_user else 0)
        ctx_url = url if url is not None else ""
        context = ErrorContext(user_id=ctx_user_id, url=ctx_url)
        structured_logger.log_error(e, context=context, include_traceback=True)
        await message.answer("❌ حدث خطأ غير متوقع")

async def _download_and_send(
    message: Message,
    downloader,
    url: str,
    platform: str,
    status_message: types.Message,
    user_id: int = 0,
    queue_manager = None
):
    if queue_manager:
        from bot.utils.priority_queue import UserTier
        user_tier = queue_manager.get_user_tier(user_id)
        
        if user_id not in queue_manager.user_daily_downloads:
            queue_manager.user_daily_downloads[user_id] = (0, dt.now())
        
        count, date = queue_manager.user_daily_downloads[user_id]
        
        if (dt.now() - date).days >= 1:
            queue_manager.user_daily_downloads[user_id] = (0, dt.now())
            count = 0

        max_daily = _get_daily_limit()
        if not queue_manager:
            max_daily = _get_daily_limit()
        else:
            max_daily = queue_manager.get_user_daily_limit(user_id)

        if count >= max_daily:
            await status_message.edit_text(get_wp_option('tk_bot_limit_msg', f"🚫 تجاوزت الحد اليومي ({max_daily} تحميل). حاول غداً.").replace('{max}', str(max_daily)))
            return
        
        current_daily = count + 1
    
    try:
        start_time = asyncio.get_event_loop().time()
        context = ErrorContext(user_id=user_id, platform=platform, url=url, action="download")
        
        if platform == 'Spotify':
            success, filename, title = await downloader.download(url)
            files = [filename] if success else []
        else:
            success, files, title = await downloader.download(url)
            if isinstance(files, str):
                files = [files]
        
        if not success or not files:
            error_msg = title if title else "حدث خطأ أثناء التحميل"
            
            # Hide detailed error messages from visitors (security)
            is_admin = settings.is_admin(user_id)
            if not is_admin:
                # Show generic message to visitors
                await status_message.edit_text(get_wp_option('tk_bot_error_msg', "❌ حدث خطأ أثناء التحميل. حاول مرة أخرى."))
            else:
                # Show detailed message to admins
                await status_message.edit_text(f"❌ {error_msg}")
            if queue_manager:
                queue_manager.stats.total_downloads += 1
                queue_manager.stats.failed_downloads += 1
            
            error = DownloadError(error_msg, context=context)
            structured_logger.log_error(error, context=context)
            return
        
        # تنظيف قائمة الملفات من القيم الفارغة أو None
        files = [f for f in files if f and isinstance(f, str)]
        
        if not files:
            logger.error(f"No valid files to send after filtering. Original files: {files}")
            await status_message.edit_text("❌ لم يتم العثور على ملفات صالحة للإرسال")
            return
        
        logger.info(f"Sending {len(files)} files: {files}")
        await _send_files(message, files, title, platform, status_message, user_id)
        
        # Record download in database
        try:
            db = DatabaseManager()
            file_size = 0
            if files and len(files) > 0:
                try:
                    for f in files:
                        if os.path.exists(f):
                            file_size += os.path.getsize(f)
                except:
                    pass
            await db.record_download(
                user_id=user_id,
                platform=platform,
                title=title,
                file_size=file_size
            )
        except Exception as e:
            logger.error(f"Failed to record download: {e}")
        
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"Download from {platform} completed in {elapsed:.1f}s")
        
        if queue_manager:
            from bot.utils.priority_queue import UserTier as PQUserTier
            queue_manager.stats.total_downloads += 1
            queue_manager.stats.successful_downloads += 1
            
            user_tier = queue_manager.get_user_tier(user_id)
            if PQUserTier and user_tier == PQUserTier.VIP:
                queue_manager.stats.vip_downloads += 1
            elif PQUserTier and user_tier == PQUserTier.PREMIUM:
                queue_manager.stats.premium_downloads += 1
            else:
                queue_manager.stats.free_downloads += 1
            
            if queue_manager.stats.successful_downloads > 0:
                total_duration = queue_manager.stats.average_time * (queue_manager.stats.successful_downloads - 1)
                queue_manager.stats.average_time = (total_duration + elapsed) / queue_manager.stats.successful_downloads
            
            if user_id in queue_manager.user_daily_downloads:
                count, date = queue_manager.user_daily_downloads[user_id]
                if (dt.now() - date).days >= 1:
                    queue_manager.user_daily_downloads[user_id] = (0, dt.now())
                else:
                    queue_manager.user_daily_downloads[user_id] = (count + 1, date)
                    queue_manager._save_daily_limits()
            else:
                queue_manager.user_daily_downloads[user_id] = (1, dt.now())
                queue_manager._save_daily_limits()
            
            queue_manager.unregister_online_user(user_id)
            queue_manager._save_stats()
        
    except Exception as e:
        logger.error(f"Error in download_and_send: {e}")
        await status_message.edit_text("❌ حدث خطأ أثناء التحميل. حاول مرة أخرى.")
        if queue_manager:
            queue_manager.stats.total_downloads += 1
            queue_manager.stats.failed_downloads += 1
            queue_manager.unregister_online_user(user_id)

async def _send_files(
    message: Message,
    files: list,
    title: Optional[str],
    platform: str,
    status_message: types.Message,
    user_id: int = 0
):
    sent_count = 0
    failed_count = 0
    
    for i, filepath in enumerate(files, 1):
        try:
            # التحقق من وجود الملف أولاً
            if not filepath or not os.path.exists(filepath):
                logger.error(f"File does not exist: {filepath}")
                await message.answer(f"❌ الملف {i} غير موجود")
                failed_count += 1
                continue

            file_size = get_file_size_mb(filepath)

            telegram_api_limit = 50
            wp_limit = _get_max_file_size_mb()
            effective_limit = min(telegram_api_limit, wp_limit)

            if file_size > effective_limit:
                await message.answer(
                    get_wp_option('tk_bot_large_file_msg', f"📦 الملف كبير جداً ({format_bytes(int(file_size * 1024 * 1024))})").replace('{size}', format_bytes(int(file_size * 1024 * 1024)))
                )
                failed_count += 1
                continue

            await status_message.edit_text(
                f"📤 جاري إرسال {sanitize_filename(title or 'الملف')} ({i}/{len(files)})..."
            )
            
            try:
                telegram_api_limit = 50

                if file_size <= telegram_api_limit:
                    if is_video_file(filepath):
                        await message.answer_video(
                            types.FSInputFile(filepath),
                            caption=f"🎬 {sanitize_filename(title or 'Video')}\n📎 المصدر: {platform}",
                            width=1920
                        )
                    elif is_audio_file(filepath):
                        await message.answer_audio(
                            types.FSInputFile(filepath),
                            title=sanitize_filename(title or "Audio"),
                            performer=platform
                        )
                    elif is_image_file(filepath):
                        await message.answer_photo(
                            types.FSInputFile(filepath),
                            caption=f"🖼️ {sanitize_filename(title or 'Image')}\n📎 المصدر: {platform}"
                        )
                    else:
                        await message.answer_document(
                            types.FSInputFile(filepath),
                            caption=f"📁 {sanitize_filename(title or 'File')}\n📎 المصدر: {platform}"
                        )
                else:
                    await message.answer_document(
                        types.FSInputFile(filepath),
                        caption=f"📁 {sanitize_filename(title or 'File')}\n📎 المصدر: {platform}\n⚠️ حجم الملف: {format_bytes(int(file_size * 1024 * 1024))}",
                        disable_content_type_detection=True
                    )

                sent_count += 1
                
            except Exception as e:
                logger.error(f"Error sending file {filepath}: {e}", exc_info=True)
                failed_count += 1

                if failed_count <= 2:
                    # عرض تفاصيل الخطأ للمساعدة في التشخيص
                    error_detail = str(e)[:100] if str(e) else "خطأ غير معروف"
                    await message.answer(f"❌ حدث خطأ أثناء إرسال الملف {i}\n🔍 السبب: {error_detail}")

            
        except Exception as e:
            logger.error(f"Error sending file {filepath}: {e}")
            failed_count += 1
            
    if sent_count > 0:
        if failed_count > 0:
            success_msg = f"✅ تم الإرسال بنجاح! ({sent_count} ملف)"
        else:
            success_msg = f"✅ تم الإرسال بنجاح!"
        await status_message.edit_text(success_msg)
    else:
        await status_message.edit_text("❌ فشل إرسال جميع الملفات")
    
    await cleanup_downloads()