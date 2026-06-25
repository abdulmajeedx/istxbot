from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

logger = logging.getLogger(__name__)

try:
    from bot.utils.translator import translate, TRANSLATION_ENABLED
except ImportError:
    TRANSLATION_ENABLED = False
    def translate(text, target_lang='ar', source_lang='auto'):
        return text


router = Router()


class TranslationStates(StatesGroup):
    """حالات الترجمة التفاعلية"""
    active = State()


def get_translation_keyboard():
    """إنشاء لوحة مفاتيح تفاعلية للترجمة"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar"),
        types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en"),
        types.InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang_fr"),
        types.InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang_es")
    )
    builder.row(
        types.InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang_de"),
        types.InlineKeyboardButton(text="🇮🇹 Italiano", callback_data="lang_it"),
        types.InlineKeyboardButton(text="🇵🇹 Português", callback_data="lang_pt"),
        types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
    )
    builder.row(
        types.InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="lang_tr"),
        types.InlineKeyboardButton(text="🇮🇳 हिन्दी", callback_data="lang_hi"),
        types.InlineKeyboardButton(text="🇨🇳 中文", callback_data="lang_zh"),
        types.InlineKeyboardButton(text="🇯🇵 日本語", callback_data="lang_ja")
    )
    builder.row(
        types.InlineKeyboardButton(text="✅ تأكيد الترجمة", callback_data="translate_confirm"),
        types.InlineKeyboardButton(text="🚪 الخروج", callback_data="translate_exit")
    )
    
    return builder.as_markup()


def get_welcome_banner():
    """إنشاء بنر الترحيب بالترجمة"""
    banner = (
        "╔══════════════════════════════════════╗\n"
        "║   🌐 جـسـلـة الـتـرجـمـة الـتـفـاعـلـيـة   ║\n"
        "╚══════════════════════════════════════╝\n\n"
        "✨ *أنت الآن في وضع الترجمة التفاعلي*\n\n"
        "📝 *كيفية الاستخدام:*\n\n"
        "1️⃣ *اكتب أي نص وسيتم ترجمته تلقائياً*\n"
        "2️⃣ *أو اختر اللغة من الأزرار بالأسفل*\n"
        "3️⃣ *أو اكتب `to:en` لتغيير اللغة*\n\n"
        "🎯 *اللغة الحالية:* `العربية (ar)`\n\n"
        "💡 *مثال:* اكتب \"Hello\" وسيتم ترجمته فوراً\n\n"
        "🚪 *للخروج:* اكتب `exit` أو `cancel`"
    )
    return banner


@router.message(F.text.startswith("/translate"))
async def cmd_translate(message: types.Message, state: FSMContext):
    """أمر الترجمة - يدخل المستخدم في جلسة الترجمة مع بنر"""
    
    if not TRANSLATION_ENABLED:
        await message.answer("❌ خدمة الترجمة غير متاحة حالياً")
        return
    
    text = message.text
    
    if text == "/translate" or text == "/translate ":
        banner = get_welcome_banner()
        keyboard = get_translation_keyboard()
        
        await state.update_data(target_lang='ar', source_lang='auto')
        await state.set_state(TranslationStates.active)
        
        await message.answer(banner, parse_mode="Markdown", reply_markup=keyboard)
        
    else:
        text_to_translate = text.replace("/translate", "").strip()
        target_lang = 'ar'
        source_lang = 'auto'
        
        if text_to_translate.lower().startswith("to:"):
            parts = text_to_translate.split(" ", 1)
            if len(parts) > 1:
                target_lang = parts[0].replace("to:", "").strip()
                text_to_translate = parts[1].strip()
        
        if not text_to_translate:
            await message.answer("❌ الرجاء كتابة النص المراد ترجمته\n\nمثال: `/translate to:en مرحبا بك`")
            return
        
        try:
            translated = translate(text_to_translate, target_lang, source_lang)
            
            if translated and translated != text_to_translate:
                result_msg = (
                    f"✅ *الترجمة*\n\n"
                    f"📝 *النص الأصلي:* {text_to_translate[:500]}\n\n"
                    f"🌐 *الترجمة:* {translated[:500]}"
                )
                await message.answer(result_msg, parse_mode="Markdown")
            else:
                await message.answer("❌ فشلت الترجمة. الرجاء المحاولة مرة أخرى.")
                
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await message.answer("❌ حدث خطأ أثناء الترجمة. الرجاء المحاولة لاحقاً.")


@router.message(TranslationStates.active)
async def handle_translation_text(message: types.Message, state: FSMContext):
    """معالجة النص في وضع الترجمة التفاعلي مع بنر"""
    
    text = message.text.strip() if message.text else ""
    
    if not text:
        return
    
    data = await state.get_data()
    target_lang = data.get('target_lang', 'ar')
    source_lang = data.get('source_lang', 'auto')
    
    if text.lower() in ['exit', 'cancel', '/cancel']:
        await message.answer("🚪 *خروج من وضع الترجمة*\n\n✨ شكراً لاستخدام خدمة الترجمة!", parse_mode="Markdown")
        await state.clear()
        return
    
    if text.lower().startswith("to:"):
        new_lang = text.replace("to:", "").strip().lower()
        
        if new_lang:
            lang_names = {
                'ar': 'العربية',
                'en': 'الإنجليزية',
                'fr': 'الفرنسية',
                'es': 'الإسبانية',
                'de': 'الألمانية',
                'it': 'الإيطالية',
                'pt': 'البرتغالية',
                'ru': 'الروسية',
                'tr': 'التركية',
                'hi': 'الهندية',
                'zh': 'الصينية',
                'ja': 'اليابانية'
            }
            
            lang_name = lang_names.get(new_lang, new_lang.upper())
            await state.update_data(target_lang=new_lang)
            
            keyboard = get_translation_keyboard()
            msg = (
                f"✅ *تم تغيير لغة الترجمة إلى: {lang_name}*\n\n"
                f"🎯 *اللغة الحالية:* `{new_lang}`\n\n"
                f"📝 *الآن اكتب النص المراد ترجمته*"
            )
            await message.answer(msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.answer("❌ *الرجاء تحديد اللغة*\n\nمثال: `to:en`", parse_mode="Markdown")
        return
    
    try:
        translated = translate(text, target_lang, source_lang)
        
        if translated and translated != text:
            lang_names = {
                'ar': 'العربية 🇸🇦',
                'en': 'الإنجليزية 🇺🇸',
                'fr': 'الفرنسية 🇫🇷',
                'es': 'الإسبانية 🇪🇸',
                'de': 'الألمانية 🇩🇪',
                'it': 'الإيطالية 🇮🇹',
                'pt': 'البرتغالية 🇵🇹',
                'ru': 'الروسية 🇷🇺',
                'tr': 'التركية 🇹🇷',
                'hi': 'الهندية 🇮🇳',
                'zh': 'الصينية 🇨🇳',
                'ja': 'اليابانية 🇯🇵'
            }
            
            target_lang_name = lang_names.get(target_lang, target_lang.upper())
            
            keyboard = get_translation_keyboard()
            result_msg = (
                f"╔══════════════════════════════════════╗\n"
                f"║       ✅ جـسـلـة الـتـرجـمـة الـفـعّـالـة       ║\n"
                f"╚══════════════════════════════════════╝\n\n"
                f"🌍 *الترجمة إلى {target_lang_name}*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 *النص الأصلي:*\n"
                f"{text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🌐 *الترجمة:*\n"
                f"{translated}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💡 *اكتب نصاً آخر للترجمة*"
            )
            await message.answer(result_msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.answer("❌ فشلت الترجمة. الرجاء المحاولة مرة أخرى.\n\n💡 *أو اكتب `exit` للخروج*", reply_markup=get_translation_keyboard())
            
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await message.answer("❌ حدث خطأ أثناء الترجمة. الرجاء المحاولة مرة أخرى.\n\n💡 *أو اكتب `exit` للخروج*")


@router.callback_query(F.data.startswith("lang_"))
async def language_callback(callback: types.CallbackQuery, state: FSMContext):
    """معالجة اختيار اللغة من الأزرار"""
    lang_code = callback.data.replace("lang_", "")
    
    lang_names = {
        'ar': 'العربية 🇸🇦',
        'en': 'الإنجليزية 🇺🇸',
        'fr': 'الفرنسية 🇫🇷',
        'es': 'الإسبانية 🇪🇸',
        'de': 'الألمانية 🇩🇪',
        'it': 'الإيطالية 🇮🇹',
        'pt': 'البرتغالية 🇵🇹',
        'ru': 'الروسية 🇷🇺',
        'tr': 'التركية 🇹🇷',
        'hi': 'الهندية 🇮🇳',
        'zh': 'الصينية 🇨🇳',
        'ja': 'اليابانية 🇯🇵'
    }
    
    await state.update_data(target_lang=lang_code)
    
    keyboard = get_translation_keyboard()
    msg = (
        f"✅ *تم اختيار اللغة: {lang_names.get(lang_code, lang_code)}*\n\n"
        f"🎯 *اللغة الحالية:* `{lang_code}`\n\n"
        f"📝 *الآن اكتب النص المراد ترجمته*"
    )
    
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "translate_confirm")
async def confirm_callback(callback: types.CallbackQuery, state: FSMContext):
    """زر تأكيد الترجمة"""
    await callback.message.answer("✅ *وضع الترجمة مفعل*\n\n📝 *اكتب أي نص للترجمة فوراً*", parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "translate_exit")
async def exit_callback(callback: types.CallbackQuery, state: FSMContext):
    """زر الخروج من الترجمة"""
    await state.clear()
    await callback.message.edit_text("🚪 *تم الخروج من وضع الترجمة*\n\n✨ شكراً لاستخدام خدمة الترجمة!\n\n📖 *للعودة:* `/translate`", parse_mode="Markdown")
    await callback.answer()


@router.message(F.text.startswith("/cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """إلغاء الجلسة الحالية"""
    current_state = await state.get_state()
    
    if current_state:
        await state.clear()
        await message.answer("✅ *تم إلغاء العملية الحالية*\n\n🚪 *عدت إلى الوضع العادي*\n\n📖 *للعودة لوضع الترجمة:* `/translate`", parse_mode="Markdown")
    else:
        await message.answer("ℹ️ *لا توجد عملية نشطة لإلغائها*", parse_mode="Markdown")
