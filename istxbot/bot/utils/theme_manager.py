"""
مدير السمات للشاشة التحكم
Theme Manager for Dashboard
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class ThemeManager:
    """مدير السمات للشاشة التحكم"""
    
    def __init__(self, theme_file: str = "dashboard_theme.json"):
        self.theme_file = theme_file
        self.theme = self._load_theme()
    
    def _load_theme(self) -> Dict[str, Any]:
        """تحميل السمة من الملف"""
        if not os.path.exists(self.theme_file):
            return self._get_default_theme()
        
        try:
            with open(self.theme_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"خطأ في تحميل السمة: {e}")
            print("استخدام السمة الافتراضية...")
            return self._get_default_theme()
    
    def _get_default_theme(self) -> Dict[str, Any]:
        """الحصول على السمة الافتراضية"""
        return {
            "theme_name": "default",
            "theme_display_name": "افتراضي",
            "colors": {
                "primary": "bright_blue",
                "secondary": "bright_green",
                "warning": "yellow",
                "error": "red",
                "info": "cyan",
                "success": "green",
                "muted": "dim",
                "bold": "bold"
            },
            "style": {
                "use_borders": True,
                "use_ascii_art": True,
                "use_colored_text": True,
                "table_box_style": "ROUNDED",
                "panel_box_style": "DOUBLE",
                "divider": "="
            },
            "ascii_art": {
                "banner": "default"
            },
            "language": "arabic",
            "refresh_interval": 30,
            "max_displayed_users": 20,
            "max_displayed_logs": 50
        }
    
    def get_color(self, color_name: str) -> str:
        """الحصول على لون"""
        return self.theme.get("colors", {}).get(color_name, "white")
    
    def get_all_colors(self) -> Dict[str, str]:
        """الحصول على جميع الألوان"""
        return self.theme.get("colors", {})
    
    def get_style(self, style_name: str) -> Any:
        """الحصول على إعداد النمط"""
        return self.theme.get("style", {}).get(style_name, None)
    
    def get_all_styles(self) -> Dict[str, Any]:
        """الحصول على جميع إعدادات النمط"""
        return self.theme.get("style", {})
    
    def get_ascii_art(self) -> str:
        """الحصول على نوع الفنون التخطيطي"""
        return self.theme.get("ascii_art", {}).get("banner", "default")
    
    def get_language(self) -> str:
        """الحصول على اللغة"""
        return self.theme.get("language", "arabic")
    
    def get_theme_name(self) -> str:
        """الحصول على اسم السمة"""
        return self.theme.get("theme_display_name", "افتراضي")
    
    def set_color(self, color_name: str, color_value: str):
        """تعيين لون"""
        if "colors" not in self.theme:
            self.theme["colors"] = {}
        
        self.theme["colors"][color_name] = color_value
        self.save_theme()
    
    def set_style(self, style_name: str, value: Any):
        """تعيين إعداد النمط"""
        if "style" not in self.theme:
            self.theme["style"] = {}
        
        self.theme["style"][style_name] = value
        self.save_theme()
    
    def set_ascii_art(self, art_type: str, art_value: str):
        """تعيين نوع الفنون التخطيطي"""
        if "ascii_art" not in self.theme:
            self.theme["ascii_art"] = {}
        
        self.theme["ascii_art"][art_type] = art_value
        self.save_theme()
    
    def set_language(self, language: str):
        """تعيين اللغة"""
        self.theme["language"] = language
        self.save_theme()
    
    def save_theme(self):
        """حفظ السمة"""
        try:
            with open(self.theme_file, 'w', encoding='utf-8') as f:
                json.dump(self.theme, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"خطأ في حفظ السمة: {e}")
    
    def reset_theme(self):
        """إعادة تعيين السمة للافتراضي"""
        self.theme = self._get_default_theme()
        self.save_theme()
        print("تم إعادة تعيين السمة للافتراضي")
    
    def reload_theme(self):
        """إعادة تحميل السمة"""
        self.theme = self._load_theme()
        print(f"تم إعادة تحميل السمة {self.get_theme_name()}")
    
    def get_theme_info(self) -> str:
        """الحصول على معلومات السمة"""
        colors = self.get_all_colors()
        styles = self.get_all_styles()
        
        info = f"""
═════════════════════════════════════════════════════════════
         معلومات السمة الحالية
═════════════════════════════════════════════════════════════
         السمة: {self.get_theme_name()}
         اللغة: {self.get_language()}
         
         الألوان:
           - Primary: {colors.get('primary')}
           - Secondary: {colors.get('secondary')}
           - Warning: {colors.get('warning')}
           - Error: {colors.get('error')}
           - Info: {colors.get('info')}
           - Success: {colors.get('success')}
           - Muted: {colors.get('muted')}
           - Bold: {colors.get('bold')}
         
         الإعدادات:
           - Borders: {'مفعلة' if styles.get('use_borders') else 'غير مفعلة'}
           - ASCII Art: {'مفعلة' if styles.get('use_ascii_art') else 'غير مفعلة'}
           - Colored Text: {'مفعلة' if styles.get('use_colored_text') else 'غير مفعلة'}
           - Table Box: {styles.get('table_box_style')}
           - Panel Box: {styles.get('panel_box_style')}
           
═════════════════════════════════════════════════════════════════
        """
        
        return info


_global_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """الحصول على مدير السمة العام"""
    global _global_theme_manager
    if _global_theme_manager is None:
        _global_theme_manager = ThemeManager()
    return _global_theme_manager
