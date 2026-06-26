"""
النواة الأساسية لقاعدة البيانات — التهيئة، الجداول، الترقيات، التنظيف، والنسخ الاحتياطي
"""

import aiosqlite
import logging
import asyncio


logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """استثناء موحد لأخطاء قاعدة البيانات"""
    pass


class DatabaseCore:
    """البنية التحتية الأساسية — الاتصال، إنشاء الجداول، والترقيات"""

    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    async def initialize(self):
        """تهيئة قاعدة البيانات وإنشاء الجداول والترقيات"""
        await self._create_tables()
        await self._migrate_add_tier_expires()
        logger.info("Database initialized successfully")

    async def _create_tables(self):
        """إنشاء كافة جداول قاعدة البيانات إذا لم تكن موجودة"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    tier TEXT DEFAULT 'FREE',
                    tier_expires_at TIMESTAMP,
                    points INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_limits (
                    user_id INTEGER PRIMARY KEY,
                    download_count INTEGER DEFAULT 0,
                    limit_date DATE DEFAULT CURRENT_DATE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_attempts (
                    user_id INTEGER PRIMARY KEY,
                    attempt_count INTEGER DEFAULT 0,
                    last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS visitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT,
                    country TEXT,
                    is_bot BOOLEAN DEFAULT 0,
                    is_premium BOOLEAN DEFAULT 0,
                    added_to_attachment_menu BOOLEAN DEFAULT 0,
                    visit_count INTEGER DEFAULT 1,
                    last_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    first_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)

            # جدول تتبع النشاط الفوري للمستخدمين
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT,
                    is_premium BOOLEAN DEFAULT 0,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    activity_type TEXT DEFAULT 'chat_open',
                    message_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS monthly_users (
                    user_id INTEGER PRIMARY KEY,
                    last_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_downloads INTEGER DEFAULT 0,
                    successful_downloads INTEGER DEFAULT 0,
                    failed_downloads INTEGER DEFAULT 0,
                    concurrent_downloads INTEGER DEFAULT 0,
                    average_time REAL DEFAULT 0.0,
                    total_wait_time REAL DEFAULT 0.0,
                    vip_downloads INTEGER DEFAULT 0,
                    premium_downloads INTEGER DEFAULT 0,
                    free_downloads INTEGER DEFAULT 0,
                    total_users INTEGER DEFAULT 0,
                    monthly_users INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS download_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    url TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS dead_letter_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT,
                    error_message TEXT,
                    category TEXT,
                    severity TEXT,
                    context_data TEXT,
                    task_data TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ── جدول سجل عمليات الشبح (Ghost Mode Audit Log) ──
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ghost_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_token TEXT,
                    user_id INTEGER NOT NULL,
                    old_tier TEXT,
                    new_tier TEXT NOT NULL,
                    expires_in INTEGER,
                    action_type TEXT DEFAULT 'set_tier',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # الفهارس لتحسين الأداء
            await db.execute("CREATE INDEX IF NOT EXISTS idx_download_tasks_user ON download_tasks(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_download_tasks_status ON download_tasks(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_visitors_user_id ON visitors(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_dead_letter_category ON dead_letter_queue(category)")

            await db.commit()

    async def _migrate_add_tier_expires(self):
        """إضافة عمود tier_expires_at للجداول الموجودة مسبقاً (ترقية تدريجية)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("ALTER TABLE users ADD COLUMN tier_expires_at TIMESTAMP")
                await db.commit()
                logger.info("Migration: added tier_expires_at column to users table")
        except Exception:
            # العمود موجود مسبقاً - لا داعي للخطأ
            pass

    async def cleanup_old_records(self, days: int = 30):
        """تنظيف السجلات القديمة من جداول المهام والطابور الميت"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                DELETE FROM download_tasks
                WHERE completed_at IS NOT NULL
                AND datetime(completed_at) < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )

            await db.execute(
                """
                DELETE FROM dead_letter_queue
                WHERE datetime(created_at) < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )

            await db.commit()
            logger.info(f"Cleaned up records older than {days} days")

    async def backup_database(self, backup_path: str) -> bool:
        """إنشاء نسخة احتياطية من ملف قاعدة البيانات"""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            return False


