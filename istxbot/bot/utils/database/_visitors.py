"""
إدارة الزوار — تسجيل، جلب، حذف، وإحصائيات الزوار
"""
import aiosqlite
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class VisitorsMixin:
    """خلط عمليات الزوار"""

    async def record_visitor(self, visitor_data: Dict) -> bool:
        """تسجيل أو تحديث معلومات الزائر"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.now().isoformat()
                await db.execute(
                    """
                    INSERT INTO visitors (
                        user_id, username, first_name, last_name, language_code,
                        country, is_bot, is_premium, added_to_attachment_menu,
                        visit_count, last_visit, first_visit
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = COALESCE(?, username),
                        first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        language_code = COALESCE(?, language_code),
                        country = COALESCE(?, country),
                        is_bot = COALESCE(?, is_bot),
                        is_premium = COALESCE(?, is_premium),
                        added_to_attachment_menu = COALESCE(?, added_to_attachment_menu),
                        visit_count = visit_count + 1,
                        last_visit = ?
                    """,
                    (
                        visitor_data.get('user_id'),
                        visitor_data.get('username'),
                        visitor_data.get('first_name'),
                        visitor_data.get('last_name'),
                        visitor_data.get('language_code'),
                        visitor_data.get('country'),
                        visitor_data.get('is_bot', 0),
                        visitor_data.get('is_premium', 0),
                        visitor_data.get('added_to_attachment_menu', 0),
                        now, now,
                        visitor_data.get('username'),
                        visitor_data.get('first_name'),
                        visitor_data.get('last_name'),
                        visitor_data.get('language_code'),
                        visitor_data.get('country'),
                        visitor_data.get('is_bot', 0),
                        visitor_data.get('is_premium', 0),
                        visitor_data.get('added_to_attachment_menu', 0),
                        now
                    )
                )
                await db.commit()
                logger.info(f"Recorded visitor {visitor_data.get('user_id')}")
                return True
        except Exception as e:
            logger.error(f"Error recording visitor: {e}")
            return False

    async def get_visitor(self, user_id: int) -> Optional[Dict]:
        """جلب معلومات زائر محدد"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM visitors WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'user_id': row[1],
                        'username': row[2],
                        'first_name': row[3],
                        'last_name': row[4],
                        'language_code': row[5],
                        'country': row[6],
                        'is_bot': row[7],
                        'is_premium': row[8],
                        'added_to_attachment_menu': row[9],
                        'visit_count': row[10],
                        'last_visit': row[11],
                        'first_visit': row[12]
                    }
                return None

    async def delete_visitor(self, user_id: int) -> bool:
        """حذف زائر من قاعدة البيانات"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM visitors WHERE user_id = ?", (user_id,))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting visitor {user_id}: {e}")
            return False

    async def get_all_visitors(self, limit: int = 100) -> List[Dict]:
        """جلب جميع الزوار"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """
                    SELECT * FROM visitors
                    ORDER BY last_visit DESC
                    LIMIT ?
                    """,
                    (limit,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            'id': row[0],
                            'user_id': row[1],
                            'username': row[2],
                            'first_name': row[3],
                            'last_name': row[4],
                            'language_code': row[5],
                            'country': row[6],
                            'is_bot': row[7],
                            'is_premium': row[8],
                            'added_to_attachment_menu': row[9],
                            'visit_count': row[10],
                            'last_visit': row[11],
                            'first_visit': row[12]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting all visitors: {e}")
            return []

    async def get_visitors_stats(self) -> Dict:
        """جلب إحصائيات الزوار"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """
                    SELECT
                        COUNT(*) as total_visitors,
                        SUM(visit_count) as total_visits,
                        COUNT(DISTINCT country) as unique_countries,
                        SUM(CASE WHEN is_premium = 1 THEN 1 ELSE 0 END) as premium_users,
                        SUM(CASE WHEN is_bot = 1 THEN 1 ELSE 0 END) as bot_count
                    FROM visitors
                    """
                ) as cursor:
                    row = await cursor.fetchone()
                    return {
                        'total_visitors': row[0] or 0,
                        'total_visits': row[1] or 0,
                        'unique_countries': row[2] or 0,
                        'premium_users': row[3] or 0,
                        'bot_count': row[4] or 0
                    }
        except Exception as e:
            logger.error(f"Error getting visitors stats: {e}")
            return {
                'total_visitors': 0, 'total_visits': 0,
                'unique_countries': 0, 'premium_users': 0, 'bot_count': 0
            }
