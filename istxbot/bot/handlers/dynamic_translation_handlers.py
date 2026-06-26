from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

logger = logging.getLogger(__name__)

try:

        auto_translate,
        translate,
        detect_language,
        TRANSLATION_ENABLED,
        get_translation_manager
    )
except ImportError:
    TRANSLATION_ENABLED = False
    def auto_translate(text, user_id):
        return text, text, 'unknown', 'ar', 'Unknown'
    def translate(text, target_lang='ar', source_lang='auto'):
        return text
    def detect_language(text):
        return 'unknown'
    def get_translation_manager():
        return None


router = Router()


class DynamicTranslationStates(StatesGroup):
    """حالات الترجمة الديناميكية"""
    active = State()


# الأوامر المستثناة من الترجمة
EXCLUDED_COMMANDS = {'/start', '/help', '/translate', '/cancel', '/exit', '/stop', '/stats'}


def get_dynamic_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """إنشاء لوحة مفاتيح تفاعلية للترجمة الديناميكية"""
    manager = get_translation_manager()
    mode = 'تلقائي' if manager and manager.get_user_preference(user_id, 'translation_mode') == 'auto' else 'يدوي'
    
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(text="🔄 تبديل الوضع (حالي: {})".format(mode), callback_data="toggle_mode"),
        types.InlineKeyboardButton(text="📊 الإحصائيات", callback_data="show_stats")
    )
    builder.row(
        types.InlineKeyboardButton(text="🇸🇦 العربية → 🇺🇸 English", callback_data="set_direction_ar_en"),
        types.InlineKeyboardButton(text="🇺🇸 English → 🇸🇦 العربية", callback_data="set_direction_en_ar")
    )
    builder.row(
        types.InlineKeyboardButton(text="⏱️ تحديث المهلة", callback_data="refresh_timeout")
    )
    builder.row(
        types.InlineKeyboardButton(text="🚪 إيقاف الترجمة", callback_data="stop_translation")
    )
    
    return builder.as_markup()


def get_session_banner(user_id: int, remaining_time: int = 0) -> str:
    """إنشاء بنر جلسة الترجمة الديناميكية"""
    minutes = remaining_time // 60
    seconds = remaining_time % 60
    
    time_str = f"{minutes}د {seconds}ث" if remaining_time > 0 else "نشطة"
    
    banner = (
        "╔═══════════════════════════════════════════╗\n"
        "║      🌐 جـلـسـة الـتـرجـمـة الـديـنـامـيـكـيـة      ║\n"
        "╚═══════════════════════════════════════════╝\n\n"
        "✨ *وضع الترجمة التلقائي مفعل*\n\n"
        "📝 *كيفية الاستخدام:*\n\n"
        "1️⃣ *اكتب أي نص وسيتم ترجمته تلقائياً*\n"
        "2️⃣ *الترجمة الذكية بين العربية والإنجليزية*\n"
        "3️⃣ *استخدم الأزرار للتحكم*\n\n"
        "⏱️ *وقت الجلسة المتبقي:* `{}`\n\n"
        "💡 *مثال:*\n"
        "   أنت: \"Hello world\"\n"
        "   أنا: ترجمته إلى العربية فوراً\n\n"
        "⚠️ *ملاحظة:* الأوامر مثل /start, /help لا تُترجم\n\n"
        "🚪 *للإيقاف:* اضغط على زر الإيقاف أو اكتب `/stop`"
    ).format(time_str)
    
    return banner


@router.message(F.text.startswith("/translate"))
async def cmd_dynamic_translate(message: types.Message, state: FSMContext):
    """أمر الترجمة الديناميكية - يدخل المستخدم في جلسة ترجمة ذكية"""
    
    if not TRANSLATION_ENABLED:
        await message.answer("❌ خدمة الترجمة غير متاحة حالياً")
        return
    
    manager = get_translation_manager()
    if manager:
        manager.set_user_preference(message.from_user.id, {
            'translation_mode': 'auto',
            'target_lang': None
        })
        manager.update_session_timeout(message.from_user.id)
    
    banner = get_session_banner(message.from_user.id, 30 * 60)
    keyboard = get_dynamic_keyboard(message.from_user.id)
    
    await state.set_state(DynamicTranslationStates.active)
    
    await message.answer(banner, parse_mode="Markdown", reply_markup=keyboard)


@router.message(DynamicTranslationStates.active)
async def handle_dynamic_translation(message: types.Message, state: FSMContext):
    """معالجة الترجمة الديناميكية للنصوص"""
    
    if not message.text:
        return
    
    text = message.text.strip()
    user_id = message.from_user.id
    
    # تحديث مهلة الجلسة
    manager = get_translation_manager()
    if manager:
        manager.update_session_timeout(user_id)
        remaining_time = manager.get_session_remaining_time(user_id)
    else:
        remaining_time = 0
    
    # التحقق من الأوامر المستثناة
    if text.lower() in ['/stop', '/exit', '/cancel']:
        await message.answer("🚪 *تم إيقاف جلسة الترجمة الديناميكية*\n\n✨ شكراً لاستخدام خدمة الترجمة!", parse_mode="Markdown")
        
        if manager:
            manager.clear_session(user_id)
        
        await state.clear()
        return
    
    # الأوامر المستثناة - لا تترجم
    if text.lower().startswith('/') and text.lower() in EXCLUDED_COMMANDS:
        await message.answer(f"ℹ️ *الأمر `{text}` مستثنى من الترجمة*\n\n💡 *يمكنك استخدامه مباشرة*", parse_mode="Markdown")
        return
    
    try:
        # الترجمة التلقائية الذكية
        original, translated, detected_lang, target_lang, direction = auto_translate(text, user_id)
        
        if translated and translated != original:
            word_count = len(text.split())
            
            lang_emojis = {
                'ar': '🇸🇦',
                'en': '🇺🇸',
                'fr': '🇫🇷',
                'es': '🇪🇸',
                'de': '🇩🇪',
                'it': '🇮🇹',
                'pt': '🇵🇹',
                'ru': '🇷🇺',
                'tr': '🇹🇷'
            }
            
            detected_emoji = lang_emojis.get(detected_lang, '🌍')
            target_emoji = lang_emojis.get(target_lang, '🌍')
            
            keyboard = get_dynamic_keyboard(user_id)
            
            result_msg = (
                f"╔═══════════════════════════════════════════╗\n"
                f"║          ✅ تـرجـمـة دينـامـيـكـيـة          ║\n"
                f"╚═══════════════════════════════════════════╝\n\n"
                f"🔄 {direction} {detected_emoji} → {target_emoji}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 *النص الأصلي* ({detected_lang.upper()}):\n"
                f"{original}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🌐 *الترجمة* ({target_lang.upper()}):\n"
                f"{translated}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 *عدد الكلمات:* `{word_count}`\n"
                f"⏱️ *وقت الجلسة المتبقي:* `{remaining_time // 60}د {remaining_time % 60}ث`"
            )
            
            await message.answer(result_msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.answer(
                "❌ فشلت الترجمة. الرجاء المحاولة مرة أخرى.\n\n"
                "💡 *أو اضغط على زر الإيقاف للخروج*",
                reply_markup=get_dynamic_keyboard(user_id)
            )
            
    except Exception as e:
        logger.error(f"Dynamic translation error: {e}")
        await message.answer(
            "❌ حدث خطأ أثناء الترجمة. الرجاء المحاولة مرة أخرى.\n\n"
            "💡 *أو اضغط على زر الإيقاف للخروج*",
            reply_markup=get_dynamic_keyboard(user_id)
        )


@router.callback_query(F.data.startswith("toggle_mode"))
async def toggle_mode_callback(callback: types.CallbackQuery, state: FSMContext):
    """تبديل بين الوضع التلقائي واليدوي"""
    user_id = callback.from_user.id
    manager = get_translation_manager()
    
    if manager:
        current_mode = manager.get_user_preference(user_id, 'translation_mode', 'auto')
        new_mode = 'manual' if current_mode == 'auto' else 'auto'
        manager.set_user_preference(user_id, {'translation_mode': new_mode})
        
        mode_text = 'تلقائي' if new_mode == 'auto' else 'يدوي'
        await callback.answer(f"تم التبديل إلى الوضع {mode_text}")
        
        keyboard = get_dynamic_keyboard(user_id)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    else:
        await callback.answer("❌ حدث خطأ")


@router.callback_query(F.data == "show_stats")
async def show_stats_callback(callback: types.CallbackQuery, state: FSMContext):
    """عرض إحصائيات المستخدم"""
    user_id = callback.from_user.id
    manager = get_translation_manager()
    
    if manager:
        stats = manager.get_user_stats(user_id)
        total_translations = stats.get('total_translations', 0)
        total_words = stats.get('total_words', 0)
        last_activity = stats.get('last_activity')
        
        if last_activity:
            activity_str = last_activity.strftime("%Y-%m-%d %H:%M:%S")
        else:
            activity_str = "غير مسجل"
        
        stats_msg = (
            "╔═══════════════════════════════════════════╗\n"
            "║           📊 إحـصـائـيـات الـتـرجـمـة          ║\n"
            "╚═══════════════════════════════════════════╝\n\n"
            f"📝 *إجمالي الترجمات:* `{total_translations}`\n"
            f"📊 *إجمالي الكلمات:* `{total_words}`\n"
            f"⏰ *آخر نشاط:* `{activity_str}`\n\n"
            f"📈 *متوسط الكلمات لكل ترجمة:* `{total_words // max(total_translations, 1)}`"
        )
        
        await callback.message.edit_text(stats_msg, parse_mode="Markdown", reply_markup=get_dynamic_keyboard(user_id))
    else:
        await callback.answer("❌ حدث خطأ")


@router.callback_query(F.data.startswith("set_direction_"))
async def set_direction_callback(callback: types.CallbackQuery, state: FSMContext):
    """تحديد اتجاه الترجمة يدوياً"""
    user_id = callback.from_user.id
    manager = get_translation_manager()
    
    if manager:
        direction = callback.data.replace("set_direction_", "")
        
        if direction == "ar_en":
            manager.set_user_preference(user_id, {
                'translation_mode': 'manual',
                'target_lang': 'en'
            })
            await callback.answer("تم تحديد الترجمة: العربية → الإنجليزية")
        elif direction == "en_ar":
            manager.set_user_preference(user_id, {
                'translation_mode': 'manual',
                'target_lang': 'ar'
            })
            await callback.answer("تم تحديد الترجمة: الإنجليزية → العربية")
        
        keyboard = get_dynamic_keyboard(user_id)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    else:
        await callback.answer("❌ حدث خطأ")


@router.callback_query(F.data == "refresh_timeout")
async def refresh_timeout_callback(callback: types.CallbackQuery, state: FSMContext):
    """تحديث مهلة الجلسة"""
    user_id = callback.from_user.id
    manager = get_translation_manager()
    
    if manager:
        manager.update_session_timeout(user_id)
        remaining_time = manager.get_session_remaining_time(user_id)
        minutes = remaining_time // 60
        seconds = remaining_time % 60
        
        await callback.answer(f"تم تحديث المهلة! الوقت المتبقي: {minutes}د {seconds}ث")
    else:
        await callback.answer("❌ حدث خطأ")


@router.callback_query(F.data == "stop_translation")
async def stop_translation_callback(callback: types.CallbackQuery, state: FSMContext):
    """زر إيقاف الترجمة"""
    user_id = callback.from_user.id
    manager = get_translation_manager()
    
    if manager:
        manager.clear_session(user_id)
    
    await state.clear()
    await callback.message.edit_text("🚪 *تم إيقاف جلسة الترجمة الديناميكية*\n\n✨ شكراً لاستخدام خدمة الترجمة!\n\n📖 *للعودة:* `/translate`", parse_mode="Markdown")
    await callback.answer()


