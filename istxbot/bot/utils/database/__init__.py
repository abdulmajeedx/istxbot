"""
مدير قاعدة البيانات الموحد — يجمع كل وحدات قاعدة البيانات في كلاس واحد
للاستخدام: from bot.utils.database import DatabaseManager, init_database, DatabaseError
"""
import asyncio
import logging
from typing import Optional

from ._base import DatabaseCore, DatabaseError
from ._users import UserMixin
from ._auth import AuthMixin
from ._downloads import DownloadsMixin
from ._visitors import VisitorsMixin
from ._ghost import GhostMixin

logger = logging.getLogger(__name__)


class DatabaseManager(
    GhostMixin,
    VisitorsMixin,
    DownloadsMixin,
    AuthMixin,
    UserMixin,
    DatabaseCore,
):
    """
    مدير قاعدة البيانات الموحد — يجمع كل العمليات في واجهة واحدة.

    ترتيب الوراثة (MRO):
        GhostMixin → VisitorsMixin → DownloadsMixin → AuthMixin → UserMixin → DatabaseCore

    جميع الاستيرادات القديمة متوافقة تماماً:
        from bot.utils.database import DatabaseManager, init_database, DatabaseError
    """
    pass


# ═══ Singleton وإدارة global ═══

_global_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """جلب النسخة العامة من مدير قاعدة البيانات (Singleton)"""
    global _global_db_manager
    if _global_db_manager is None:
        _global_db_manager = DatabaseManager()
    return _global_db_manager


async def init_database(db_path: str = "bot_data.db") -> DatabaseManager:
    """تهيئة النسخة العامة من مدير قاعدة البيانات"""
    global _global_db_manager
    _global_db_manager = DatabaseManager(db_path)
    await _global_db_manager.initialize()
    return _global_db_manager
