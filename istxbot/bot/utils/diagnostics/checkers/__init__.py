"""
مسجلات الفاحصين — كل فاحص يرجع قائمة من Issue
"""
from .api_mismatch import check_api_mismatch
from .code_quality import check_code_quality
from .structure import check_structure
from .security import check_security
from .git_hooks import check_git
from .config import check_config

ALL_CHECKERS = [
    ("api", check_api_mismatch, "تطابق API"),
    ("code_quality", check_code_quality, "جودة الكود"),
    ("structure", check_structure, "الهيكلة"),
    ("security", check_security, "الأمان"),
    ("git", check_git, "Git"),
    ("config", check_config, "الإعدادات"),
]
