import logging
from typing import Optional
from datetime import datetime, timedelta
import asyncio

TRANSLATION_ENABLED = False
GT = None

try:
    from deep_translator import GoogleTranslator
    GT = GoogleTranslator
    TRANSLATION_ENABLED = True
except ImportError:
    pass

LANGUAGE_DETECTION_ENABLED = False

try:
    from langdetect import detect as lang_detect
    LANGUAGE_DETECTION_ENABLED = True
except ImportError:
    def lang_detect(text):
        return 'unknown'

logger = logging.getLogger(__name__)


class TranslationManager:
    def __init__(self):
        self._translator_cache = {}
        self.user_preferences = {}
        self.user_stats = {}
        self.session_timeouts = {}
    
    def set_user_preference(self, user_id: int, preference: dict):
        """حفظ تفضيلات المستخدم"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        self.user_preferences[user_id].update(preference)
        logger.debug(f"Updated preferences for user {user_id}: {preference}")
    
    def get_user_preference(self, user_id: int, key: str, default=None):
        """الحصول على تفضيلات المستخدم"""
        if user_id not in self.user_preferences:
            return default
        return self.user_preferences[user_id].get(key, default)
    
    def increment_user_stats(self, user_id: int, word_count: int = 0):
        """زيادة إحصائيات المستخدم"""
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                'total_translations': 0,
                'total_words': 0,
                'last_activity': datetime.now()
            }
        
        self.user_stats[user_id]['total_translations'] += 1
        self.user_stats[user_id]['total_words'] += word_count
        self.user_stats[user_id]['last_activity'] = datetime.now()
    
    def get_user_stats(self, user_id: int) -> dict:
        """الحصول على إحصائيات المستخدم"""
        return self.user_stats.get(user_id, {
            'total_translations': 0,
            'total_words': 0,
            'last_activity': None
        })
    
    def update_session_timeout(self, user_id: int):
        """تحديث مهلة الجلسة"""
        self.session_timeouts[user_id] = datetime.now()
    
    def is_session_active(self, user_id: int, timeout_minutes: int = 30) -> bool:
        """التحقق من أن الجلسة نشطة"""
        if user_id not in self.session_timeouts:
            return False
        
        timeout = self.session_timeouts[user_id] + timedelta(minutes=timeout_minutes)
        return datetime.now() < timeout
    
    def get_session_remaining_time(self, user_id: int, timeout_minutes: int = 30) -> int:
        """الحصول على الوقت المتبقي للجلسة"""
        if user_id not in self.session_timeouts:
            return 0
        
        timeout = self.session_timeouts[user_id] + timedelta(minutes=timeout_minutes)
        remaining = timeout - datetime.now()
        return max(0, int(remaining.total_seconds()))
    
    def clear_session(self, user_id: int):
        """مسح جلسة المستخدم"""
        if user_id in self.session_timeouts:
            del self.session_timeouts[user_id]
    
    def translate(self, text: str, target_lang: str = 'ar', source_lang: str = 'auto') -> Optional[str]:
        """ترجمة النص إلى اللغة المحددة"""
        if not TRANSLATION_ENABLED:
            logger.warning("Translation is not enabled")
            return text
        
        try:
            if not text or not text.strip():
                return text
            
            cache_key = f"{source_lang}_{target_lang}_{hash(text)}"
            
            if cache_key in self._translator_cache:
                return self._translator_cache[cache_key]
            
            translator = GT(source=source_lang, target=target_lang)
            translated = translator.translate(text)
            
            if len(self._translator_cache) > 1000:
                self._translator_cache.clear()
            
            self._translator_cache[cache_key] = translated
            return translated
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text
    
    def auto_translate(self, text: str, user_id: int) -> tuple:
        """
        ترجمة تلقائية ذكية
        
        يعود: (النص الأصلي, الترجمة, اللغة المكتشفة, اللغة الهدف, الاتجاه)
        """
        if not TRANSLATION_ENABLED:
            return text, text, 'unknown', 'ar', 'Unknown'
        
        try:
            detected_lang = self.detect_language(text)
            
            mode = self.get_user_preference(user_id, 'translation_mode', 'auto')
            
            if mode == 'auto':
                if detected_lang == 'ar':
                    target_lang = 'en'
                    direction = 'AR → EN'
                elif detected_lang == 'en':
                    target_lang = 'ar'
                    direction = 'EN → AR'
                else:
                    target_lang = 'ar'
                    direction_str = f'{detected_lang} → AR'
                    direction = direction_str.upper() if detected_lang != 'unknown' else 'Unknown'
            else:
                target_lang = self.get_user_preference(user_id, 'target_lang', 'en')
                if target_lang:
                    if detected_lang == 'ar':
                        direction = f'AR → {target_lang.upper()}'
                    else:
                        direction_str = f'{detected_lang} → {target_lang}'
                        direction = direction_str.upper() if detected_lang != 'unknown' else 'Unknown'
                else:
                    target_lang = 'en'
                    direction = 'Unknown'
            
            translated = self.translate(text, target_lang, detected_lang)
            
            word_count = len(text.split())
            self.increment_user_stats(user_id, word_count)
            
            return text, translated, detected_lang, target_lang, direction
            
        except Exception as e:
            logger.error(f"Auto translation error: {e}")
            return text, text, 'unknown', 'ar', 'Unknown'
    
    def detect_language(self, text: str) -> str:
        """كشف لغة النص"""
        if not LANGUAGE_DETECTION_ENABLED:
            return 'unknown'
        
        try:
            return lang_detect(text)
        except:
            return 'unknown'
    
    def split_text(self, text: str, max_length: int = 5000) -> list:
        """تقسيم النصوص الطويلة"""
        if len(text) <= max_length:
            return [text]
        
        parts = []
        sentences = text.split('. ')
        current_part = ""
        
        for sentence in sentences:
            if len(current_part + sentence) <= max_length:
                current_part += sentence + '. '
            else:
                if current_part:
                    parts.append(current_part.strip())
                current_part = sentence + '. '
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts


_translation_manager = None

def get_translation_manager():
    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager()
    return _translation_manager

def translate(text: str, target_lang: str = 'ar', source_lang: str = 'auto') -> Optional[str]:
    """وظيفة مساعدة للترجمة"""
    if not TRANSLATION_ENABLED:
        return text
    
    manager = get_translation_manager()
    return manager.translate(text, target_lang, source_lang)

def auto_translate(text: str, user_id: int) -> tuple:
    """وظيفة مساعدة للترجمة التلقائية"""
    manager = get_translation_manager()
    return manager.auto_translate(text, user_id)

def detect_language(text: str) -> str:
    """وظيفة مساعدة لكشف اللغة"""
    manager = get_translation_manager()
    return manager.detect_language(text)
