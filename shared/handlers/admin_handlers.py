from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import logging
import os
import asyncio
from datetime import datetime
from config.settings import settings, get_wp_option
from bot.utils.database import get_db_manager

try:
    from bot.utils.priority_queue import get_queue_manager, UserTier
    PRIORITY_QUEUE_ENABLED = True
except ImportError:
    PRIORITY_QUEUE_ENABLED = False

admin_router = Router()
logger = logging.getLogger(__name__)

BANNED_USERS_FILE = "banned_users.txt"

def load_banned_users() -> set:
    """تحميل قائمة المحظورين"""
    try:
        if os.path.exists(BANNED_USERS_FILE):
            with open(BANNED_USERS_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    return set(map(int, content.split('\n')))
        return set()
    except Exception as e:
        logger.error(f"Error loading banned users: {e}")
    return set()

def save_banned_users(banned_users: set):
    """حفظ قائمة المحظورين"""
    try:
        with open(BANNED_USERS_FILE, 'w') as f:
            f.write('\n'.join(map(str, banned_users)))
    except Exception as e:
        logger.error(f"Error saving banned users: {e}")

def is_banned(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم محظوراً"""
    banned_users = load_banned_users()
    return user_id in banned_users

def is_admin_check(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم أدمن"""
    return settings.is_admin(user_id)

@admin_router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    db = get_db_manager()
    divider = "━━━━━━━━━━━━━━"
    
    try:
        stats = await db.get_stats()
        visitors = await db.get_visitors_stats()
        total_users = visitors.get('total_visitors', 0)
        total_downloads = stats.get('total_downloads', 0)
        monthly_users = stats.get('monthly_users', 0)
        
        dtoday = 0
        try:
            import aiosqlite as _sql
            async with _sql.connect(db.db_path) as conn:
                async with conn.execute("SELECT COUNT(*) FROM downloads WHERE date(downloaded_at) = date('now')") as c:
                    row = await c.fetchone()
                    dtoday = row[0] if row else 0
                async with conn.execute("SELECT COUNT(DISTINCT user_id) FROM visitors WHERE last_visit >= datetime('now', '-30 minutes')") as c:
                    row = await c.fetchone()
                    online = row[0] if row else 0
        except:
            dtoday = 0
            online = 0
        
        banned_count = len(load_banned_users())
        
        stats_text = (
            f"📊 <b>إحصائيات البوت</b>\n\n"
            f"{divider}\n\n"
            f"📥 <b>التحميلات</b>\n"
            f"  • اليوم: <b>{dtoday}</b>\n"
            f"  • الإجمالي: <b>{total_downloads}</b>\n\n"
            f"👥 <b>المستخدمون</b>\n"
            f"  • الإجمالي: <b>{total_users}</b>\n"
            f"  • هذا الشهر: <b>{monthly_users}</b>\n"
            f"  • متواجدون الآن: <b>{online}</b>\n\n"
            f"🚫 المحظورون: <b>{banned_count}</b>\n\n"
            f"{divider}\n"
            f"⚙️ لوحة التحكم: inspiredownloader.com/wp-admin/\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    except Exception as e:
        stats_text = f"❌ خطأ في الإحصائيات: {e}"
    
    await message.answer(stats_text)

def format_admin_panel(title: str, sections: list[tuple[str, list[str]]]) -> str:
    """تنسيق لوحة تحكم الأدمن بشكل جميل"""
    divider = "━" * 20
    parts = [f"🔧 *{title}*", "", divider, ""]
    
    for section_title, commands in sections:
        parts.append(f"• *{section_title}*")
        for cmd in commands:
            parts.append(f"  {cmd}")
        parts.append("")
    
    parts.append(divider)
    parts.append("💡 اضغط على أي أمر لاستخدامه")
    return "\n".join(parts)

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    sections = [
        ("📊 الإحصائيات", [
            "`/stats` - إحصائيات البوت",
        ]),
        ("👥 إدارة المستخدمين", [
            "`/ban <id>` - حظر مستخدم",
            "`/unban <id>` - إلغاء حظر",
            "`/list_banned` - قائمة المحظورين",
        ]),
        ("📢 المراسلة", [
            "`/broadcast <msg>` - إرسال للجميع",
        ]),
    ]
    
    admin_text = format_admin_panel("لوحة تحكم الأدمن", sections)
    await message.answer(admin_text, parse_mode="Markdown")

@admin_router.message(Command("users"))
async def cmd_users(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    banned_users = load_banned_users()
    divider = "━" * 20
    
    users_text = f"👥 *إدارة المستخدمين*\n\n{divider}\n\n"
    
    if PRIORITY_QUEUE_ENABLED:
        queue_manager = get_queue_manager()
        if queue_manager:
            try:
                status = await queue_manager.get_queue_status(user_id)
                users_text += "📊 *الإحصائيات*\n"
                users_text += f"  • 🟢 المتواجدون: {status['online_users']}\n"
                users_text += f"  • 📅 هذا الشهر: {status['monthly_users']}\n"
                users_text += f"  • 📊 الإجمالي: {queue_manager.stats.total_users}\n\n"
            except:
                pass
    
    users_text += "🔒 *الأمان*\n"
    users_text += f"  • 🚫 المحظورون: {len(banned_users)}\n"
    users_text += f"  • 👤 الأدمن: `{settings.ADMIN_ID}`\n\n"
    
    users_text += f"{divider}\n\n"
    
    users_text += "💡 *أوامر الحظر*\n"
    users_text += "  `/ban <id>` - حظر مستخدم\n"
    users_text += "  `/unban <id>` - إلغاء حظر\n"
    users_text += "  `/list_banned` - قائمة المحظورين\n\n"
    
    users_text += "📅 *أوامر الزوار*\n"
    users_text += "  `/visitors` - زوار اليوم\n"
    users_text += "  `/visitors 7` - آخر 7 أيام\n"
    users_text += "  `/visitors month` - هذا الشهر\n\n"
    
    if PRIORITY_QUEUE_ENABLED:
        users_text += "🎯 *أوامر المستويات*\n"
        users_text += "  `/settier <id> <tier>` - تغيير المستوى\n"
        users_text += "  `/addpoints <id> <pts>` - إضافة نقاط\n"
    
    await message.answer(users_text, parse_mode="Markdown")

@admin_router.message(Command("reload"))
async def cmd_reload(message: Message):
    """إعادة تحميل الإعدادات من وورد بريس"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return

    await message.answer("🔄 *جاري إعادة تحميل الإعدادات...*", parse_mode="Markdown")
    
    try:
        updates = []
        new_token = get_wp_option('tk_bot_token', '')
        if new_token and new_token != settings.BOT_TOKEN:
            settings.BOT_TOKEN = new_token
            updates.append(f"🔑 التوكن: `{new_token[:15]}...`")
        
        new_ids = get_wp_option('tk_bot_admin_ids', '')
        if new_ids:
            try:
                ids = [int(x.strip()) for x in new_ids.split('\n') if x.strip()]
                if ids and ids[0] != settings.ADMIN_ID:
                    settings.ADMIN_ID = ids[0]
                    updates.append(f"👤 الأدمن: `{ids[0]}`")
            except: pass

        new_platforms = get_wp_option('tk_bot_supported_platforms', '')
        if new_platforms:
            pl = [p.strip() for p in new_platforms.split(',') if p.strip()]
            settings.SUPPORTED_PLATFORMS = pl
            updates.append(f"📱 المنصات: {', '.join(pl)}")

        new_limit = get_wp_option('tk_bot_max_file_size', '')
        if new_limit:
            try:
                sz = int(new_limit)
                if sz != settings.MAX_FILE_SIZE_MB:
                    settings.MAX_FILE_SIZE_MB = sz
                    updates.append(f"📦 حجم الملف: {sz}MB")
            except: pass

        if updates:
            msg = "✅ *تم تحديث الإعدادات:*\n\n" + "\n".join(updates)
            msg += "\n\n💡 المصدر: inspiredownloader.com"
        else:
            msg = "✅ *الإعدادات محدثة بالفعل*\n\nلا توجد تغييرات جديدة من وورد بريس"
        
        await message.answer(msg, parse_mode="Markdown")
        logger.info(f"Settings reloaded by admin {user_id}: {len(updates)} changes")
    except Exception as e:
        await message.answer(f"❌ خطأ: {str(e)[:200]}")

@admin_router.message(Command("settings"))
async def cmd_settings(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    divider = "━" * 20
    settings_text = f"⚙️ *إعدادات البوت*\n\n{divider}\n\n"
    
    settings_text += "📁 *الملفات*\n"
    settings_text += f"  • حجم الملف: {settings.MAX_FILE_SIZE_MB}MB\n"
    settings_text += f"  • مجلد التحميل: `{settings.DOWNLOAD_DIR}`\n"
    settings_text += f"  • FFmpeg: `{settings.FFMPEG_PATH}`\n\n"
    
    settings_text += "⏱️ *الأداء*\n"
    settings_text += f"  • مهلة التحميل: {settings.DOWNLOAD_TIMEOUT}s\n\n"
    
    settings_text += "👤 *الأدمن*\n"
    settings_text += f"  • المعرف: `{settings.ADMIN_ID}`\n\n"
    
    if PRIORITY_QUEUE_ENABLED:
        queue_manager = get_queue_manager()
        if queue_manager:
            settings_text += f"{divider}\n\n"
            settings_text += "� *قائمة الانتظار*\n"
            settings_text += f"  • التحميلات المتزامنة: {queue_manager.max_concurrent}\n"
            settings_text += f"  • حجم القائمة: {queue_manager.max_queue}\n"
            settings_text += f"  • المهلة: {queue_manager.timeout}s\n"
            settings_text += f"  • النقاط: {'✅' if queue_manager.enable_points else '❌'}\n"
    
    await message.answer(settings_text, parse_mode="Markdown")

@admin_router.message(F.text.startswith("/broadcast "))
async def cmd_broadcast(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    broadcast_msg = message.text[11:].strip()
    if not broadcast_msg:
        await message.answer("💡 *الاستخدام:* `/broadcast رسالة`\n\nمثال: `/broadcast مرحباً بالجميع!`")
        return
    
    await message.answer(f"📢 *جاري إرسال الرسالة للمستخدمين...*\n\n{broadcast_msg}")
    
    try:
        bot = message.bot
        db_manager = get_db_manager()
        visitors = await db_manager.get_all_visitors(limit=1000)
        
        if not visitors:
            await message.answer("❌ لا يوجد مستخدمين لإرسال الرسالة")
            return
        
        success_count = 0
        failed_count = 0
        
        for visitor in visitors:
            try:
                target_user_id = visitor['user_id']
                
                banned_users = load_banned_users()
                if target_user_id in banned_users:
                    logger.debug(f"Skipping banned user {target_user_id}")
                    continue
                
                await bot.send_message(target_user_id, f"📢 {broadcast_msg}")
                success_count += 1
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {visitor['user_id']}: {e}")
                failed_count += 1
        
        result_text = f"✅ *تم إرسال الرسالة*\n\n"
        result_text += f"✓ نجحت: {success_count}\n"
        result_text += f"✗ فشلت: {failed_count}\n"
        result_text += f"📊 الإجمالي: {len(visitors)}\n\n"
        result_text += f"📩 *الرسالة:*\n{broadcast_msg}"
        
        await message.answer(result_text, parse_mode="Markdown")
        logger.info(f"Broadcast sent by admin {user_id}: {success_count} successful, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}")
        await message.answer(f"❌ حدث خطأ أثناء إرسال الرسالة: {e}")

@admin_router.message(F.text.startswith("/user_info "))
async def cmd_user_info(message: Message):
    """عرض معلومات مفصلة عن مستخدم معين"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer("💡 *الاستخدام:* `/user_info <user_id>`")
        return
    
    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("❌ يجب إدخال معرف المستخدم (رقم)")
        return
    
    try:
        db_manager = get_db_manager()
        visitor = await db_manager.get_visitor(target_user_id)
        
        if not visitor:
            await message.answer(f"❌ *المستخدم `{target_user_id}` غير موجود في قاعدة البيانات*")
            return
        
        info_text = f"👤 *معلومات المستخدم*\n\n"
        info_text += f"🆔 *المعرف:* `{visitor['user_id']}`\n"
        info_text += f"👤 *الاسم:* {visitor['first_name'] or 'غير محدد'}"
        if visitor['last_name']:
            info_text += f" {visitor['last_name']}"
        if visitor['username']:
            info_text += f"\n🔗 *اليوزرنيم:* @{visitor['username']}"
        info_text += f"\n🌍 *الدولة:* {visitor['country']}"
        info_text += f"\n🗣️ *اللغة:* {visitor['language_code']}"
        info_text += f"\n👥 *عدد الزيارات:* {visitor['visit_count']}"
        info_text += f"\n📅 *أول زيارة:* {visitor['first_visit']}"
        info_text += f"\n📅 *آخر زيارة:* {visitor['last_visit']}"
        if visitor['is_premium']:
            info_text += "\n💎 *حساب مميز*"
        if visitor['is_bot']:
            info_text += "\n🤖 *بوت*"
        
        banned_users = load_banned_users()
        if target_user_id in banned_users:
            info_text += "\n🚫 *مستخدم محظور*"
        else:
            info_text += "\n✅ *نشط*"
        
        if PRIORITY_QUEUE_ENABLED:
            queue_manager = get_queue_manager()
            if queue_manager:
                user_tier = queue_manager.get_user_tier(target_user_id)
                user_points = queue_manager.get_user_points(target_user_id)
                info_text += f"\n👑 *المستوى:* {user_tier.name}"
                info_text += f"\n💎 *النقاط:* {user_points}"
        
        await message.answer(info_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error showing user info: {e}")
        await message.answer("❌ حدث خطأ أثناء جلب معلومات المستخدم")

@admin_router.message(Command("list_banned"))
async def cmd_list_banned(message: Message):
    """عرض قائمة المستخدمين المحظورين"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    try:
        banned_users = load_banned_users()
        
        if not banned_users:
            await message.answer("✅ *لا يوجد مستخدمين محظورين*")
            return
        
        db_manager = get_db_manager()
        banned_text = f"🚫 *قائمة المحظورين* ({len(banned_users)} مستخدم)\n\n"
        
        for ban_user_id in sorted(banned_users):
            visitor = await db_manager.get_visitor(ban_user_id)
            if visitor:
                name = visitor['first_name'] or 'بدون اسم'
                username = f" (@{visitor['username']})" if visitor['username'] else ""
                banned_text += f"• `{ban_user_id}` - {name}{username}\n"
            else:
                banned_text += f"• `{ban_user_id}` - معلومات غير متوفرة\n"
        
        await message.answer(banned_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error listing banned users: {e}")
        await message.answer("❌ حدث خطأ أثناء جلب قائمة المحظورين")

@admin_router.message(Command("clearcache"))
async def cmd_clearcache(message: Message):
    """مسح الذاكرة المؤقتة"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    await message.answer("🧹 *جاري مسح الذاكرة المؤقتة...*")
    
    try:
        import gc
        gc.collect()
        
        await message.answer("✅ *تم مسح الذاكرة المؤقتة بنجاح*")
        logger.info(f"Cache cleared by admin {user_id}")
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        await message.answer("❌ حدث خطأ أثناء مسح الذاكرة المؤقتة")

@admin_router.message(Command("health"))
async def cmd_health(message: Message):
    """فحص صحة النظام"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    try:
        import psutil
        
        divider = "━" * 20
        health_text = f"🏥 *صحة النظام*\n\n{divider}\n\n"
        
        health_text += "💻 *النظام*\n"
        health_text += f"  • 🧠 CPU: {psutil.cpu_percent()}%\n"
        health_text += f"  • 💾 RAM: {psutil.virtual_memory().percent}%\n"
        health_text += f"  • 💿 Disk: {psutil.disk_usage('/').percent}%\n\n"
        
        health_text += "⚙️ *البوت*\n"
        health_text += f"  • 👤 الأدمن: `{settings.ADMIN_ID}`\n"
        health_text += f"  • 📂 التحميلات: `{settings.DOWNLOAD_DIR}`\n"
        
        if PRIORITY_QUEUE_ENABLED:
            queue_manager = get_queue_manager()
            if queue_manager:
                status = await queue_manager.get_queue_status(user_id)
                health_text += f"  • � نشطة: {status['active_downloads']}\n"
                health_text += f"  • ⏳ انتظار: {status['queue_size']}\n"
        
        banned_users = load_banned_users()
        health_text += f"  • 🚫 محظورون: {len(banned_users)}\n\n"
        
        health_text += f"{divider}\n"
        health_text += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await message.answer(health_text, parse_mode="Markdown")
        
    except ImportError:
        await message.answer("⚠️ مكتبة psutil غير متوفرة\n\n`pip install psutil`")
    except Exception as e:
        logger.error(f"Error checking health: {e}")
        await message.answer("❌ حدث خطأ أثناء فحص صحة النظام")

if PRIORITY_QUEUE_ENABLED:
    @admin_router.message(F.text.startswith("/resetpoints "))
    async def cmd_resetpoints(message: Message):
        """تصفير نقاط مستخدم"""
        user_id = message.from_user.id if message.from_user else 0
        if not is_admin_check(user_id):
            return
        
        try:
            args = message.text[12:].strip().split()
            if len(args) != 1:
                await message.answer("💡 *الاستخدام:* `/resetpoints user_id`")
                return
            
            target_user_id = int(args[0])
            
            queue_manager = get_queue_manager()
            if queue_manager:
                queue_manager.add_user_points(target_user_id, -queue_manager.get_user_points(target_user_id))
                await message.answer(f"✅ *تم تصفير نقاط المستخدم* `{target_user_id}`")
                logger.info(f"Reset points for user {target_user_id} by admin {user_id}")
        except ValueError:
            await message.answer("❌ يجب إدخال رقم مستخدم صحيح")
        except Exception as e:
            logger.error(f"Error resetting points: {e}")
            await message.answer("❌ حدث خطأ أثناء تصفير النقاط")
    
    @admin_router.message(Command("queue_status"))
    async def cmd_queue_status(message: Message):
        """عرض حالة قائمة الانتظار"""
        user_id = message.from_user.id if message.from_user else 0
        if not is_admin_check(user_id):
            return
        
        try:
            queue_manager = get_queue_manager()
            if not queue_manager:
                await message.answer("❌ نظام قائمة الانتظار غير مفعّل")
                return
            
            status = await queue_manager.get_queue_status(user_id)
            divider = "━" * 20
            
            status_text = f"📋 *قائمة الانتظار*\n\n{divider}\n\n"
            
            status_text += "📊 *الإحصائيات*\n"
            status_text += f"  • 📥 الإجمالي: {status['total_downloads']}\n"
            status_text += f"  • ✅ ناجحة: {status['successful_downloads']}\n"
            status_text += f"  • ❌ فاشلة: {status['failed_downloads']}\n\n"
            
            status_text += "⚡ *الحالة الحالية*\n"
            status_text += f"  • 🔄 نشطة: {status['active_downloads']}\n"
            status_text += f"  • ⏳ انتظار: {status['queue_size']}\n"
            status_text += f"  • ⏱️ المتوسط: {status['average_time']}\n\n"
            
            status_text += f"{divider}\n\n"
            
            status_text += "⚙️ *الإعدادات*\n"
            status_text += f"  • المتزامنة: {queue_manager.max_concurrent}\n"
            status_text += f"  • حجم القائمة: {queue_manager.max_queue}\n"
            status_text += f"  • المهلة: {queue_manager.timeout}s\n"
            status_text += f"  • النقاط: {'✅' if queue_manager.enable_points else '❌'}\n\n"
            
            status_text += f"{divider}\n"
            status_text += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await message.answer(status_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error showing queue status: {e}")
            await message.answer("❌ حدث خطأ أثناء جلب حالة قائمة الانتظار")

@admin_router.message(F.text.startswith("/ban "))
async def cmd_ban(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    try:
        user_id_ban = int(message.text[5:].strip())
        
        banned_users = load_banned_users()
        banned_users.add(user_id_ban)
        save_banned_users(banned_users)
        
        await message.answer(f"🚫 *تم حظر المستخدم* `{user_id_ban}`\n\n✅ تمت الإضافة إلى قائمة المحظورين")
        logger.info(f"User {user_id_ban} banned by admin {user_id}")
    except ValueError:
        await message.answer("❌ يجب إدخال رقم مستخدم صحيح")
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        await message.answer("❌ حدث خطأ أثناء حظر المستخدم")

@admin_router.message(F.text.startswith("/unban "))
async def cmd_unban(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    try:
        user_id_unban = int(message.text[7:].strip())
        
        banned_users = load_banned_users()
        if user_id_unban in banned_users:
            banned_users.remove(user_id_unban)
            save_banned_users(banned_users)
            await message.answer(f"✅ *تم إلغاء حظر المستخدم* `{user_id_unban}`\n\n🟢 تمت الإزالة من قائمة المحظورين")
            logger.info(f"User {user_id_unban} unbanned by admin {user_id}")
        else:
            await message.answer(f"⚠️ المستخدم `{user_id_unban}` غير محظور")
    except ValueError:
        await message.answer("❌ يجب إدخال رقم مستخدم صحيح")
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        await message.answer("❌ حدث خطأ أثناء إلغاء الحظر")

@admin_router.message(Command("logs"))
async def cmd_logs(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    logs_text = "📋 *السجلات الحالية*\n\n"
    
    if PRIORITY_QUEUE_ENABLED:
        queue_manager = get_queue_manager()
        if queue_manager:
            status = await queue_manager.get_queue_status(user_id)
            logs_text += f"📥 *التحميلات النشطة:* {status['active_downloads']}\n"
            logs_text += f"⏳ *في القائمة:* {status['queue_size']}\n"
            logs_text += f"✅ *ناجحة:* {status['successful_downloads']}\n"
            logs_text += f"❌ *فاشلة:* {status['failed_downloads']}\n\n"
    
    logs_text += f"👤 *معرف الأدمن:* {settings.ADMIN_ID}\n"
    logs_text += f"⏰ *آخر تحديث:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    banned_users = load_banned_users()
    logs_text += f"🚫 *المحظورون:* {len(banned_users)}\n"
    
    await message.answer(logs_text, parse_mode="Markdown")

@admin_router.message(Command("restart"))
async def cmd_restart(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    await message.answer("🔄 *جاري إعادة تشغيل البوت...*\n\n⏳ الرجاء الانتظار...")
    logger.info(f"Bot restart requested by admin {user_id}")

@admin_router.message(Command("shutdown"))
async def cmd_shutdown(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    await message.answer("⛔ *جاري إيقاف البوت...*\n\n👋 إلى اللقاء!")
    logger.info(f"Bot shutdown requested by admin {user_id}")

if PRIORITY_QUEUE_ENABLED:
    @admin_router.message(F.text.startswith("/settier "))
    async def cmd_settier(message: Message):
        user_id = message.from_user.id if message.from_user else 0
        if not is_admin_check(user_id):
            return
        
        try:
            args = message.text[9:].strip().split()
            if len(args) != 2:
                await message.answer("💡 *الاستخدام:* `/settier user_id tier`\n\nالمستويات: VIP, PREMIUM, STANDARD, FREE\nمثال: `/settier 123456 VIP`")
                return
            
            target_user_id = int(args[0])
            tier_name = args[1].upper()
            
            tier_map = {
                'VIP': UserTier.VIP,
                'PREMIUM': UserTier.PREMIUM,
                'STANDARD': UserTier.STANDARD,
                'FREE': UserTier.FREE,
            }
            
            if tier_name not in tier_map:
                await message.answer("❌ المستوى غير صحيح. المستويات المتاحة: VIP, PREMIUM, STANDARD, FREE")
                return
            
            queue_manager = get_queue_manager()
            if queue_manager:
                queue_manager.set_user_tier(target_user_id, tier_map[tier_name])
                await message.answer(f"✅ *تم تغيير مستوى المستخدم* `{target_user_id}`\n\n👑 المستوى الجديد: {tier_name}")
                logger.info(f"User {target_user_id} tier changed to {tier_name} by admin {user_id}")
        except ValueError:
            await message.answer("❌ يجب إدخال رقم مستخدم صحيح")
        except Exception as e:
            logger.error(f"Error setting tier: {e}")
            await message.answer("❌ حدث خطأ أثناء تغيير المستوى")
    
    @admin_router.message(F.text.startswith("/addpoints "))
    async def cmd_addpoints(message: Message):
        user_id = message.from_user.id if message.from_user else 0
        if not is_admin_check(user_id):
            return
        
        try:
            args = message.text[10:].strip().split()
            if len(args) != 2:
                await message.answer("💡 *الاستخدام:* `/addpoints user_id points`\n\nمثال: `/addpoints 123456 50`")
                return
            
            target_user_id = int(args[0])
            points = int(args[1])
            
            if points <= 0:
                await message.answer("❌ عدد النقاط يجب أن يكون أكبر من 0")
                return
            
            queue_manager = get_queue_manager()
            if queue_manager:
                queue_manager.add_user_points(target_user_id, points)
                current_points = queue_manager.get_user_points(target_user_id)
                await message.answer(f"✅ *تم إضافة {points} نقطة للمستخدم* `{target_user_id}`\n\n💎 الرصيد الجديد: {current_points} نقطة")
                logger.info(f"Added {points} points to user {target_user_id} by admin {user_id}")
        except ValueError:
            await message.answer("❌ يجب إدخال أرقام صحيحة")
        except Exception as e:
            logger.error(f"Error adding points: {e}")
            await message.answer("❌ حدث خطأ أثناء إضافة النقاط")

@admin_router.message(Command("visitors"))
async def cmd_visitors(message: Message):
    """عرض الزوار المسجلين"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    args = message.text.split()
    limit = 20
    
    if len(args) > 1:
        try:
            limit = int(args[1])
            if limit <= 0 or limit > 100:
                await message.answer("❌ عدد الزوار يجب أن يكون بين 1 و 100")
                return
        except ValueError:
            await message.answer("❌ يجب إدخال رقم صحيح")
            return
    
    try:
        db_manager = get_db_manager()
        visitors = await db_manager.get_all_visitors(limit)
        
        if not visitors:
            await message.answer("📭 *لا يوجد زوار مسجلين*")
            return
        
        visitors_text = f"👥 *الزوار المسجلين* (آخر {len(visitors)} زائر)\n\n"
        
        for i, visitor in enumerate(visitors, 1):
            visitor_text = f"{i}. *{visitor['first_name'] or 'بدون اسم'}*"
            if visitor['username']:
                visitor_text += f" (@{visitor['username']})"
            visitor_text += f"\n   🆔: `{visitor['user_id']}`"
            visitor_text += f"\n   🌍: {visitor['country']}"
            visitor_text += f"\n   👥: {visitor['visit_count']} زيارة"
            if visitor['is_premium']:
                visitor_text += " 💎"
            visitor_text += f"\n   📅: {visitor['last_visit'][:10]}"
            visitor_text += "\n"
            
            if len(visitors_text + visitor_text) > 4000:
                await message.answer(visitors_text, parse_mode="Markdown")
                visitors_text = visitor_text
            else:
                visitors_text += visitor_text
        
        if visitors_text:
            await message.answer(visitors_text, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error showing visitors: {e}")
        await message.answer("❌ حدث خطأ أثناء جلب الزوار")

@admin_router.message(Command("visitor_stats"))
async def cmd_visitor_stats(message: Message):
    """عرض إحصائيات الزوار"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    try:
        db_manager = get_db_manager()
        stats = await db_manager.get_visitors_stats()
        divider = "━" * 20
        
        stats_text = f"📊 *إحصائيات الزوار*\n\n{divider}\n\n"
        
        stats_text += "👥 *الزوار*\n"
        stats_text += f"  • الإجمالي: {stats['total_visitors']}\n"
        stats_text += f"  • الزيارات: {stats['total_visits']}\n\n"
        
        stats_text += "🌍 *التوزيع*\n"
        stats_text += f"  • الدول: {stats['unique_countries']}\n"
        stats_text += f"  • مميزون: {stats['premium_users']}\n"
        stats_text += f"  • بوتات: {stats['bot_count']}\n\n"
        
        stats_text += f"{divider}\n"
        stats_text += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await message.answer(stats_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error showing visitor stats: {e}")
        await message.answer("❌ حدث خطأ أثناء جلب الإحصائيات")

@admin_router.message(Command("visitor_info"))
async def cmd_visitor_info(message: Message):
    """عرض معلومات زائر معين"""
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin_check(user_id):
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer("💡 *الاستخدام:* `/visitor_info <user_id>`")
        return
    
    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("❌ يجب إدخال معرف المستخدم (رقم)")
        return
    
    try:
        db_manager = get_db_manager()
        visitor = await db_manager.get_visitor(target_user_id)
        
        if not visitor:
            await message.answer(f"❌ *المستخدم `{target_user_id}` غير موجود في قاعدة البيانات*")
            return
        
        info_text = f"👤 *معلومات الزائر*\n\n"
        info_text += f"🆔 *المعرف:* `{visitor['user_id']}`\n"
        info_text += f"👤 *الاسم:* {visitor['first_name'] or 'بدون اسم'}"
        if visitor['last_name']:
            info_text += f" {visitor['last_name']}"
        if visitor['username']:
            info_text += f"\n🔗 *اليوزرنيم:* @{visitor['username']}"
        info_text += f"\n🌍 *الدولة:* {visitor['country']}"
        info_text += f"\n🗣️ *اللغة:* {visitor['language_code']}"
        info_text += f"\n👥 *عدد الزيارات:* {visitor['visit_count']}"
        info_text += f"\n📅 *أول زيارة:* {visitor['first_visit']}"
        info_text += f"\n📅 *آخر زيارة:* {visitor['last_visit']}"
        if visitor['is_premium']:
            info_text += "\n💎 *حساب مميز*"
        if visitor['is_bot']:
            info_text += "\n🤖 *بوت*"
        
        banned_users = load_banned_users()
        if target_user_id in banned_users:
            info_text += "\n🚫 *مستخدم محظور*"
        else:
            info_text += "\n✅ *نشط*"
        
        if PRIORITY_QUEUE_ENABLED:
            queue_manager = get_queue_manager()
            if queue_manager:
                user_tier = queue_manager.get_user_tier(target_user_id)
                user_points = queue_manager.get_user_points(target_user_id)
                info_text += f"\n👑 *المستوى:* {user_tier.name}"
                info_text += f"\n💎 *النقاط:* {user_points}"
        
        await message.answer(info_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error showing visitor info: {e}")
        await message.answer("❌ حدث خطأ أثناء جلب معلومات الزائر")

@admin_router.message(Command("2fa"))
async def cmd_2fa(message: Message):
    """إرسال كود التحقق بخطوتين إلى الإدارة"""
    user_id = message.from_user.id if message.from_user else 0
    
    # Only admin can use this command
    if user_id != 1368279990:  # Change this to your admin Telegram ID
        await message.answer("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    try:
        # Read 2FA code from file
        TWO_FA_FILE = "data/runtime/2fa_code.txt"
        
        if not os.path.exists(TWO_FA_FILE):
            await message.answer("❌ لا يوجد كود تحقق حالياً")
            await message.answer("💡 *الطريقة:*")
            await message.answer("1. انتقل إلى لوحة التحكم")
            await message.answer("2. أدخل اسم المستخدم وكلمة المرور")
            await message.answer("3. سيتم إنشاء كود التحقق")
            await message.answer("4. سيظهر الكود هنا تلقائياً")
            return
        
        with open(TWO_FA_FILE, 'r') as f:
            lines = f.readlines()
            
        if not lines or len(lines) < 2:
            await message.answer("❌ لا يوجد كود تحقق صحيح")
            return
        
        code = lines[0].strip()
        
        # Get timestamp (second line)
        try:
            timestamp = lines[1].strip()
        except:
            timestamp = datetime.now().isoformat()
        
        # Calculate remaining time
        try:
            created_at = datetime.fromisoformat(timestamp)
            time_left = 300 - (datetime.now() - created_at).total_seconds()
            time_left = max(0, int(time_left))
            minutes = time_left // 60
            seconds = time_left % 60
        except:
            minutes = 5
            seconds = 0
        
        # Send the 2FA code
        message_text = f"🔐 *كود التحقق بخطوتين (2FA)*\n\n"
        message_text += f"🔢 *الكود:* `{code}`\n\n"
        message_text += f"⏱️ *صالح لمدة:* {minutes} دقيقة {seconds} ثانية\n\n"
        message_text += f"⚠️ *هذا الكود ساري فقط مرة واحدة*\n\n"
        message_text += f"💡 *للدخول إلى لوحة التحكم:*"
        message_text += f"  http://your-server-ip:8081/login-2fa"
        message_text += f"  أو: http://localhost:8081/login-2fa\n\n"
        message_text += f"📝 *أدخل الكود في الصفحة المطلوبة*"
        
        await message.answer(message_text, parse_mode="Markdown")
        logger.info(f"2FA code sent to admin {user_id} via /2fa command")
        
    except FileNotFoundError:
        await message.answer("❌ لا يوجد ملف كود التحقق")
        logger.error(f"2FA file not found for admin {user_id}")
    except Exception as e:
        logger.error(f"Error sending 2FA code: {e}")
        await message.answer(f"❌ حدث خطأ أثناء إرسال كود التحقق: {e}")