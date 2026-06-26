"""
عمليات التحميل — تسجيل التحميلات، المهام، الطابور الميت، والإحصائيات
"""
import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class DownloadsMixin:
    """خلط عمليات التحميل والإحصائيات"""

    async def record_download(
        self,
        user_id: int,
        platform: str,
        title: str = None,
        file_size: int = 0,
        file_path: str = None
    ) -> bool:
        """تسجيل تحميل في قاعدة البيانات وتحديث إحصائيات المستخدم"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # إنشاء جدول التحميلات إذا لم يكن موجوداً
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        platform TEXT,
                        title TEXT,
                        file_size INTEGER,
                        file_path TEXT,
                        downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                """)

                # إضافة عمود total_downloads لجدول المستخدمين إذا لم يكن موجوداً
                try:
                    await db.execute("ALTER TABLE users ADD COLUMN total_downloads INTEGER DEFAULT 0")
                except Exception:
                    pass  # العمود موجود مسبقاً

                # تسجيل التحميل
                await db.execute("""
                    INSERT INTO downloads (user_id, platform, title, file_size, file_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, platform, title, file_size, file_path))

                # تحديث إجمالي تحميلات المستخدم
                await db.execute("""
                    UPDATE users SET total_downloads = COALESCE(total_downloads, 0) + 1
                    WHERE user_id = ?
                """, (user_id,))

                # إنشاء المستخدم إذا لم يكن موجوداً
                await db.execute("""
                    INSERT OR IGNORE INTO users (user_id, total_downloads)
                    VALUES (?, 1)
                """, (user_id,))

                await db.commit()
                logger.info(f"Recorded download for user {user_id} from {platform}")
                return True
        except Exception as e:
            logger.error(f"Error recording download: {e}")
            return False

    async def get_user_downloads(self, user_id: int, limit: int = 20) -> List[Dict]:
        """جلب سجل تحميلات المستخدم"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT platform, title, file_size as size, downloaded_at as date
                    FROM downloads WHERE user_id = ?
                    ORDER BY downloaded_at DESC LIMIT ?
                """, (user_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting user downloads: {e}")
            return []

    async def get_daily_download_count(self, user_id: int) -> int:
        """جلب عدد تحميلات المستخدم اليوم"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                today = datetime.now().strftime('%Y-%m-%d')
                async with db.execute("""
                    SELECT COUNT(*) as count FROM downloads
                    WHERE user_id = ? AND date(downloaded_at) = date(?)
                """, (user_id, today)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error getting daily download count: {e}")
            return 0

    # ═══ Download Tasks Queue ═══

    async def add_download_task(self, task: Dict) -> bool:
        """إضافة مهمة تحميل إلى قاعدة البيانات"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO download_tasks
                    (task_id, user_id, url, platform, status, priority, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task['task_id'], task['user_id'], task['url'],
                        task['platform'], task.get('status', 'pending'),
                        task.get('priority', 3), datetime.now().isoformat()
                    )
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding download task: {e}")
            return False

    async def update_download_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """تحديث حالة مهمة تحميل"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                updates = []
                params = []

                if status:
                    updates.append("status = ?")
                    params.append(status)
                if started_at:
                    updates.append("started_at = ?")
                    params.append(started_at)
                if completed_at:
                    updates.append("completed_at = ?")
                    params.append(completed_at)
                if error_message:
                    updates.append("error_message = ?")
                    params.append(error_message)

                if updates:
                    params.append(task_id)
                    query = f"UPDATE download_tasks SET {', '.join(updates)} WHERE task_id = ?"
                    await db.execute(query, params)
                    await db.commit()
                    return True
            return False
        except Exception as e:
            logger.error(f"Error updating download task: {e}")
            return False

    # ═══ Dead Letter Queue ═══

    async def add_to_dead_letter_queue(self, error_entry: Dict) -> bool:
        """إضافة إدخال خطأ إلى الطابور الميت"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO dead_letter_queue
                    (error_type, error_message, category, severity, context_data, task_data, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        error_entry.get('error_type'),
                        error_entry.get('message'),
                        error_entry.get('category'),
                        error_entry.get('severity'),
                        json.dumps(error_entry.get('context', {})),
                        json.dumps(error_entry.get('task_data', {})),
                        error_entry.get('retry_count', 0)
                    )
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding to dead letter queue: {e}")
            return False

    async def get_dead_letter_entries(self, limit: int = 10) -> List[Dict]:
        """جلب إدخالات الطابور الميت"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM dead_letter_queue
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'error_type': row[1],
                        'error_message': row[2],
                        'category': row[3],
                        'severity': row[4],
                        'context': json.loads(row[5]) if row[5] else {},
                        'task_data': json.loads(row[6]) if row[6] else {},
                        'retry_count': row[7],
                        'created_at': row[8]
                    }
                    for row in rows
                ]

    # ═══ Statistics ═══

    async def get_stats(self) -> Dict:
        """جلب إحصائيات التحميل"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT total_downloads, successful_downloads, failed_downloads,
                       concurrent_downloads, average_time, total_wait_time,
                       vip_downloads, premium_downloads, free_downloads,
                       total_users, monthly_users
                FROM stats
                WHERE id = 1
                """
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'total_downloads': row[0] or 0,
                        'successful_downloads': row[1] or 0,
                        'failed_downloads': row[2] or 0,
                        'concurrent_downloads': row[3] or 0,
                        'average_time': row[4] or 0.0,
                        'total_wait_time': row[5] or 0.0,
                        'vip_downloads': row[6] or 0,
                        'premium_downloads': row[7] or 0,
                        'free_downloads': row[8] or 0,
                        'total_users': row[9] or 0,
                        'monthly_users': row[10] or 0
                    }
                return {
                    'total_downloads': 0, 'successful_downloads': 0,
                    'failed_downloads': 0, 'concurrent_downloads': 0,
                    'average_time': 0.0, 'total_wait_time': 0.0,
                    'vip_downloads': 0, 'premium_downloads': 0,
                    'free_downloads': 0, 'total_users': 0, 'monthly_users': 0
                }

    async def update_stats(self, stats: Dict):
        """تحديث إحصائيات التحميل"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()
            await db.execute(
                """
                INSERT INTO stats (
                    id, total_downloads, successful_downloads, failed_downloads,
                    concurrent_downloads, average_time, total_wait_time,
                    vip_downloads, premium_downloads, free_downloads,
                    total_users, monthly_users, updated_at
                ) VALUES (
                    1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(id) DO UPDATE SET
                    total_downloads = ?, successful_downloads = ?, failed_downloads = ?,
                    concurrent_downloads = ?, average_time = ?, total_wait_time = ?,
                    vip_downloads = ?, premium_downloads = ?, free_downloads = ?,
                    total_users = ?, monthly_users = ?, updated_at = ?
                """,
                (
                    stats['total_downloads'], stats['successful_downloads'], stats['failed_downloads'],
                    stats['concurrent_downloads'], stats['average_time'], stats['total_wait_time'],
                    stats['vip_downloads'], stats['premium_downloads'], stats['free_downloads'],
                    stats['total_users'], stats['monthly_users'], now,
                    stats['total_downloads'], stats['successful_downloads'], stats['failed_downloads'],
                    stats['concurrent_downloads'], stats['average_time'], stats['total_wait_time'],
                    stats['vip_downloads'], stats['premium_downloads'], stats['free_downloads'],
                    stats['total_users'], stats['monthly_users'], now
                )
            )
            await db.commit()
