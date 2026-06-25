import logging
from typing import Optional

TRANSLATION_ENABLED = False
GoogleTranslator = None

try:
    from deep_translator import GoogleTranslator as GT
    GoogleTranslator = GT
    TRANSLATION_ENABLED = True
except ImportError:
    pass

try:
    from langdetect import detect as lang_detect
    LANGUAGE_DETECTION_ENABLED = True
except ImportError:
    LANGUAGE_DETECTION_ENABLED = False
    def lang_detect(text):
        return 'unknown'

logger = logging.getLogger(__name__)


class TranslationManager:
    def __init__(self):
        self._translator_cache = {}
    
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
            
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated = translator.translate(text)
            
            if len(self._translator_cache) > 1000:
                self._translator_cache.clear()
            
            self._translator_cache[cache_key] = translated
            return translated
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text
    
    def detect_language(self, text: str) -> str:
        """كشف لغة النص"""
        if not LANGUAGE_DETECTION_ENABLED:
            return 'unknown'
        
        try:
            return lang_detect(text)
        except:
            return 'unknown'


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

def detect_language(text: str) -> str:
    """وظيفة مساعدة لكشف اللغة"""
    manager = get_translation_manager()
    return manager.detect_language(text)
