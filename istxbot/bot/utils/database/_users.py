"""
عمليات المستخدمين — الإنشاء، التحديث، النقاط، الحدود اليومية، المستخدمين الشهريين
"""
import aiosqlite
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class UserMixin:
    """خلط عمليات المستخدمين الأساسية"""

    # يعتمد على self.db_path من الكلاس الأساسي DatabaseCore

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """جلب معلومات المستخدم"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'tier': row[3],
                        'tier_expires_at': row[4],
                        'points': row[5],
                        'created_at': row[6],
                        'updated_at': row[7]
                    }
                return None

    async def create_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        tier: str = 'FREE',
        points: int = 0
    ) -> bool:
        """إنشاء مستخدم جديد"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO users (user_id, username, first_name, tier, points)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, username, first_name, tier, points)
                )
                await db.commit()
                logger.info(f"Created user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False

    async def update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        tier: Optional[str] = None,
        tier_expires_at: Optional[str] = None,
        points: Optional[int] = None,
        clear_tier_expiry: bool = False
    ) -> bool:
        """تحديث معلومات المستخدم - يدعم تاريخ انتهاء الصلاحية ومسحه"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                update_fields = []
                params = []

                if username is not None:
                    update_fields.append("username = ?")
                    params.append(username)
                if first_name is not None:
                    update_fields.append("first_name = ?")
                    params.append(first_name)
                if tier is not None:
                    update_fields.append("tier = ?")
                    params.append(tier)
                if tier_expires_at is not None:
                    update_fields.append("tier_expires_at = ?")
                    params.append(tier_expires_at)
                elif clear_tier_expiry:
                    # مسح تاريخ انتهاء الصلاحية صراحةً (للترقية الدائمة)
                    update_fields.append("tier_expires_at = NULL")
                if points is not None:
                    update_fields.append("points = ?")
                    params.append(points)

                update_fields.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(user_id)

                if update_fields:
                    query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
                    await db.execute(query, params)
                    await db.commit()
                    return True
            return False
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False

    async def update_user_activity(self, user_id: int) -> bool:
        """تحديث آخر نشاط للمستخدم"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET updated_at = ? WHERE user_id = ?",
                    (datetime.now().isoformat(), user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")
            return False

    async def get_daily_limit(self, user_id: int) -> Optional[Dict]:
        """جلب حد التحميل اليومي للمستخدم"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM daily_limits WHERE limit_date < date('now', '-1 day')")

            async with db.execute(
                """
                SELECT user_id, download_count, limit_date
                FROM daily_limits
                WHERE user_id = ? AND limit_date = date('now')
                """,
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'user_id': row[0],
                        'download_count': row[1],
                        'limit_date': row[2]
                    }
                return None

    async def increment_daily_downloads(self, user_id: int) -> int:
        """زيادة عداد التحميل اليومي للمستخدم"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM daily_limits WHERE limit_date < date('now', '-1 day')")

            await db.execute(
                """
                INSERT INTO daily_limits (user_id, download_count, limit_date)
                VALUES (?, 1, date('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    download_count = download_count + 1,
                    limit_date = date('now')
                """,
                (user_id,)
            )
            await db.commit()

            async with db.execute(
                "SELECT download_count FROM daily_limits WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_user_points(self, user_id: int) -> int:
        """جلب نقاط المستخدم"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT points FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def add_user_points(self, user_id: int, points: int) -> bool:
        """إضافة نقاط للمستخدم"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    UPDATE users
                    SET points = points + ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (points, datetime.now().isoformat(), user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding points: {e}")
            return False

    async def update_monthly_visit(self, user_id: int):
        """تحديث زيارة المستخدم الشهرية"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO monthly_users (user_id, last_visit)
                VALUES (?, ?)
                """,
                (user_id, datetime.now().isoformat())
            )
            await db.commit()

    async def get_monthly_users_count(self) -> int:
        """جلب عدد المستخدمين الشهريين"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                DELETE FROM monthly_users
                WHERE last_visit < datetime('now', '-30 days')
                """
            )

            async with db.execute("SELECT COUNT(*) FROM monthly_users") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def _get_all_users(self, limit: int = 100) -> List[Dict]:
        """جلب جميع المستخدمين (للاستخدام الداخلي)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """
                    SELECT user_id, username, first_name, tier, points, created_at
                    FROM users
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1],
                            'first_name': row[2],
                            'tier': row[3],
                            'points': row[4],
                            'created_at': row[5]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
