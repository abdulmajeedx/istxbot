from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
import logging
import asyncio
import os
from typing import Optional
from datetime import datetime as dt

from bot.utils.database import DatabaseManager

from bot.downloaders.instagram_downloader import InstagramDownloader
from bot.downloaders.snapchat_downloader import SnapchatDownloader
from bot.downloaders.tiktok_downloader import TikTokDownloader
from bot.downloaders.pinterest_downloader import PinterestDownloader
from bot.downloaders.twitter_downloader import TwitterDownloader
from bot.downloaders.facebook_downloader import FacebookDownloader
from bot.downloaders.youtube_downloader import YtDlpDownloader
from bot.downloaders.spotify_downloader import SpotifyDownloader

# Try to import improved TikTok downloader
ImprovedTikTokDownloader = None
try:

    IMPROVED_TIKTOK_ENABLED = True
except ImportError:
    IMPROVED_TIKTOK_ENABLED = False

TikTokAPIDownloader = None
try:

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
from config.settings import settings

try:
    from bot.utils.priority_queue import get_queue_manager, UserTier as PQUserTier
    PRIORITY_QUEUE_ENABLED = True
    UserTier = PQUserTier
except ImportError:
    PRIORITY_QUEUE_ENABLED = False
    UserTier = None

router = Router()
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

instagram_dl = InstagramDownloader()
snapchat_dl = SnapchatDownloader()
tiktok_dl = TikTokDownloader()
pinterest_dl = PinterestDownloader()
twitter_dl = TwitterDownloader()
facebook_dl = FacebookDownloader()
youtube_dl = YtDlpDownloader()
spotify_dl = SpotifyDownloader()

logger.info("✓ Using TikTok Yt-DLP Downloader")

SUPPORTED_PLATFORMS = {
    'TikTok': tiktok_dl,
    'Twitter': twitter_dl,
    'Instagram': instagram_dl,
    'Snapchat': snapchat_dl,
    'Pinterest': pinterest_dl,
    'Facebook': facebook_dl,
    'Spotify': spotify_dl,
    'YouTube': youtube_dl,
}

# Platforms detected but handled manually
MANUAL_PLATFORMS = {
    'SoundCloud': "⚠️ منصة SoundCloud غير مدعومة حالياً.\n"
                  "جاري العمل على دعمها قريباً 🎵",
}

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
    await record_visitor(message, 'start_command')
    
    welcome_msg = format_styled_message(
        "بوت التحميل الشامل",
        [
            ("ابدأ الآن", "أرسل أي رابط فيديو/صورة من: TikTok • Twitter/X • Instagram • Snapchat • Pinterest • Facebook • Spotify • YouTube"),
            ("كيف يعمل؟", "سيتم التحميل ثم الإرسال لك مباشرة بجودة عالية مع إزالة العلامة المائية حيثما أمكن."),
            ("أوامر مفيدة", "`/help` جميع الميزات"),
            ("الدعم", "للاستفسار والدعم: @Qmrzx")
        ]
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📖 الدليل", callback_data="help"),
        InlineKeyboardButton(text="📱 المنصات المدعومة", callback_data="platforms"),
    )
    builder.row(
        InlineKeyboardButton(text="🔗 ابدأ التحميل الآن", switch_inline_query_current_chat="")
    )

    reply_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/help")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    await message.answer(welcome_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=builder.as_markup())
    await message.answer("💡 *استخدم الأزرار أدناه للوصول السريع*", parse_mode=ParseMode.MARKDOWN, reply_markup=reply_kb)

@router.message(F.text.startswith("/help"))
async def cmd_help(message: Message):
    await record_visitor(message, 'help_command')
    user_id = message.from_user.id if message.from_user else 0
    is_admin = settings.is_admin(user_id)
    
    if is_admin:
        admin_help = (
            "🔧 *أوامر الأدمن*\n\n"
            "• /stats - عرض الإحصائيات\n"
            "• /admin - عرض جميع أوامر الأدمن\n"
            "• /users - إدارة المستخدمين\n"
            "• /settings - عرض إعدادات البوت\n"
            "• /broadcast - إرسال رسالة للجميع\n"
            "• /ban - حظر مستخدم\n"
            "• /unban - إلغاء حظر مستخدم\n"
            "• /logs - عرض السجلات\n"
            "• /restart - إعادة تشغيل البوت\n"
            "• /shutdown - إيقاف البوت"
        )
        
        await message.answer(admin_help, parse_mode=ParseMode.MARKDOWN)
    else:
        user_help = format_styled_message(
            "دليل الاستخدام",
            [
                ("الخطوات", "1) انسخ الرابط\n2) أرسله هنا\n3) انتظر التحميل\n4) استلم الملف فوراً"),
                ("المنصات المدعومة", "TikTok • Twitter/X • Instagram • Snapchat • Pinterest • Facebook • Spotify • YouTube"),
                ("مزايا", "إزالة العلامة المائية حيثما أمكن، عدة جودات"),
                ("أوامر", "`/help` للمزيد")
            ],
            footer="للاستفسار والدعم: @Qmrzx"
        )

        await message.answer(user_help, parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    is_admin = settings.is_admin(user_id)
    
    if is_admin:
        admin_help = (
            "🔧 *أوامر الأدمن*\n\n"
            "• /stats - عرض الإحصائيات\n"
            "• /admin - عرض جميع أوامر الأدمن\n"
            "• /users - إدارة المستخدمين\n"
            "• /settings - عرض إعدادات البوت\n"
            "• /broadcast - إرسال رسالة للجميع\n"
            "• /ban - حظر مستخدم\n"
            "• /unban - إلغاء حظر مستخدم\n"
            "• /logs - عرض السجلات\n"
            "• /restart - إعادة تشغيل البوت\n"
            "• /shutdown - إيقاف البوت"
        )
        await callback.message.edit_text(admin_help, parse_mode=ParseMode.MARKDOWN)
    else:
        user_help = format_styled_message(
            "دليل الاستخدام",
            [
                ("الخطوات", "1) انسخ الرابط\n2) أرسله هنا\n3) انتظر التحميل\n4) استلم الملف فوراً"),
                ("المنصات المدعومة", "TikTok • Twitter/X • Instagram • Snapchat • Pinterest • Facebook • Spotify • YouTube"),
                ("مزايا", "إزالة العلامة المائية حيثما أمكن، عدة جودات"),
                ("أوامر", "`/help` للمزيد")
            ],
            footer="للاستفسار والدعم: @Qmrzx"
        )
        await callback.message.edit_text(user_help, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@router.callback_query(F.data == "platforms")
async def callback_platforms(callback: CallbackQuery):
    platforms_msg = (
        "📱 *المنصات المدعومة*\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "🎵 *TikTok*\n"
        "├ فيديوهات بدون علامة مائية\n"
        "├ صور ومعارض الصور\n"
        "└ `tiktok.com/...` / `vm.tiktok.com/...` \n\n"
        "🐦 *Twitter / X*\n"
        "├ فيديوهات وصور\n"
        "├ جودة عالية\n"
        "└ `twitter.com/...` / `x.com/...` \n\n"
        "📷 *Instagram*\n"
        "├ منشورات، Reels، قصص\n"
        "├ صور وفيديوهات\n"
        "└ `instagram.com/...` \n\n"
        "👻 *Snapchat*\n"
        "├ قصص وفيديوهات Spotlight\n"
        "├ صور\n"
        "└ `snapchat.com/...` \n\n"
        "📌 *Pinterest*\n"
        "├ صور وفيديوهات\n"
        "├ جودة أصلية\n"
        "└ `pinterest.com/...` / `pin.it/...` \n\n"
        "📘 *Facebook*\n"
        "├ فيديوهات وصور\n"
        "├ منشورات عامة\n"
        "└ `facebook.com/...` / `fb.watch/...` \n\n"
        "🎬 *YouTube*\n"
        "├ فيديوهات بجودة عالية\n"
        "├ صوتيات MP3\n"
        "└ `youtube.com/...` / `youtu.be/...` \n\n"
        "🎵 *Spotify*\n"
        "├ أغاني وبودكاست\n"
        "├ جودة عالية\n"
        "└ `spotify.com/...` / `open.spotify.com/...` \n\n"
        "━━━━━━━━━━━━━━━━\n"
        "💡 *انسخ الرابط وأرسله هنا!*"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📖 الدليل", callback_data="help"),
        InlineKeyboardButton(text="🔗 ابدأ التحميل", switch_inline_query_current_chat=""),
    )
    
    await callback.message.edit_text(platforms_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "cancel_download")
async def callback_cancel(callback: CallbackQuery):
    await callback.message.edit_text("🚫 *تم إلغاء التحميل*\n\n📌 أرسل رابطاً جديداً للبدء", parse_mode=ParseMode.MARKDOWN)
    await callback.answer("تم الإلغاء")

@router.message(F.text)
async def handle_text(message: Message):
    """Handle regular text messages (skip commands)."""
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
            welcome_msg = (
                "👋 *أهلاً بك في بوت التحميل الشامل!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📱 *المنصات المدعومة:*\n"
                "• TikTok • Twitter/X • Instagram\n"
                "• Snapchat • Pinterest • Facebook\n"
                "• Spotify • YouTube\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📌 *كيفية الاستخدام:*\n"
                "1️⃣ انسخ رابط الفيديو أو الصورة\n"
                "2️⃣ أرسله هنا مباشرة\n"
                "3️⃣ انتظر التحميل\n"
                "4️⃣ استلم الملف فوراً!\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "🔧 *أوامر:*\n"
                "• `/help` - دليل الاستخدام الكامل\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "❓ *للاستفسار والدعم:* @Qmrzx"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="📖 الدليل", callback_data="help"),
                InlineKeyboardButton(text="📱 المنصات المدعومة", callback_data="platforms"),
            )
            
            await message.answer(welcome_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=builder.as_markup())
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
        
        if platform not in SUPPORTED_PLATFORMS:
            if platform in MANUAL_PLATFORMS:
                logger.info(f"Manual platform detected: {platform} | User: {user_id}")
                await message.answer(MANUAL_PLATFORMS[platform])
                return
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
        
        status_message = await message.answer(
            f"⏳ جاري التحميل من {platform}...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_download")]
            ])
        )
        
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

        user_tier = queue_manager.get_user_tier(user_id)
        
        if user_id not in queue_manager.user_daily_downloads:
            queue_manager.user_daily_downloads[user_id] = (0, dt.now())
        
        count, date = queue_manager.user_daily_downloads[user_id]
        
        if (dt.now() - date).days >= 1:
            queue_manager.user_daily_downloads[user_id] = (0, dt.now())
            count = 0

        max_daily = queue_manager.get_user_daily_limit(user_id)

        if count >= max_daily:
            await status_message.edit_text(f"❌ تجاوزت الحد اليومي ({max_daily} تحميل). انتظر غداً أو ارتقِ للمستوى الأعلى.")
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
                await status_message.edit_text("❌ حدث خطأ أثناء التحميل. حاول مرة أخرى.")
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

            if file_size > telegram_api_limit:
                await message.answer(
                    f"⚠️ الملف {i} كبير جداً للإرسال ({format_bytes(int(file_size * 1024 * 1024))})\n"
                    f"حد Telegram API: {telegram_api_limit}MB (ثابت)\n"
                    f"💡 الملفات الأكبر من {telegram_api_limit}MB لا يمكن إرسالها عبر أي بوت تلغرام"
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحميل رابط آخر", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="📖 الدليل", callback_data="help")],
        ])
        await status_message.edit_text(success_msg, reply_markup=keyboard)
    else:
        await status_message.edit_text("❌ فشل إرسال جميع الملفات")
    
    await cleanup_downloads()


