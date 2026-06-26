"""
وضع الشبح (Ghost Mode) — سجل تدقيق العمليات الصامتة على مستويات المستخدمين
"""
import aiosqlite
import logging

from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class GhostMixin:
    """خلط عمليات سجل الشبح"""

    async def log_ghost_action(
        self,
        admin_token: str,
        user_id: int,
        old_tier: str,
        new_tier: str,
        expires_in: Optional[int] = None
    ) -> bool:
        """تسجيل عملية تغيير مستوى في وضع الشبح"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO ghost_actions (admin_token, user_id, old_tier, new_tier, expires_in)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (admin_token, user_id, old_tier, new_tier, expires_in)
                )
                await db.commit()
                logger.info(f"Ghost action logged: user={user_id} {old_tier}→{new_tier}")
                return True
        except Exception as e:
            logger.error(f"Error logging ghost action: {e}")
            return False

    async def get_ghost_actions(
        self,
        limit: int = 50,
        user_id: Optional[int] = None
    ) -> List[Dict]:
        """جلب سجل عمليات الشبح - مع إمكانية الفلترة حسب المستخدم"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if user_id:
                    async with db.execute(
                        """
                        SELECT id, admin_token, user_id, old_tier, new_tier, expires_in, action_type, created_at
                        FROM ghost_actions
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (user_id, limit)
                    ) as cursor:
                        rows = await cursor.fetchall()
                else:
                    async with db.execute(
                        """
                        SELECT id, admin_token, user_id, old_tier, new_tier, expires_in, action_type, created_at
                        FROM ghost_actions
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (limit,)
                    ) as cursor:
                        rows = await cursor.fetchall()

                return [
                    {
                        'id': row[0],
                        'admin_token': row[1],
                        'user_id': row[2],
                        'old_tier': row[3],
                        'new_tier': row[4],
                        'expires_in': row[5],
                        'action_type': row[6],
                        'created_at': row[7]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Error getting ghost actions: {e}")
            return []

