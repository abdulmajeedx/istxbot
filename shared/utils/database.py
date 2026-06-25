import sqlite3
import aiosqlite
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
from dataclasses import asdict
from contextlib import asynccontextmanager
import asyncio

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    pass


class DatabaseManager:
    """SQLite database manager for replacing JSON files"""
    
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize database and create tables"""
        await self._create_tables()
        logger.info("Database initialized successfully")
    
    async def _create_tables(self):
        """Create all necessary tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    tier TEXT DEFAULT 'FREE',
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

            await db.execute("""
                CREATE TABLE IF NOT EXISTS activation_keys (
                    key TEXT PRIMARY KEY,
                    owner_name TEXT,
                    usage_limit INTEGER DEFAULT 10,
                    usage_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    notes TEXT,
                    platform TEXT DEFAULT ''
                )
            """)

            # Add platform column if not exists (migration)
            try:
                await db.execute("ALTER TABLE activation_keys ADD COLUMN platform TEXT DEFAULT ''")
            except:
                pass

            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_keys (
                    device_id TEXT PRIMARY KEY,
                    key TEXT NOT NULL,
                    daily_limit INTEGER DEFAULT 5,
                    daily_count INTEGER DEFAULT 0,
                    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (key) REFERENCES activation_keys(key)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_download_tasks_user ON download_tasks(user_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_download_tasks_status ON download_tasks(status)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitors_user_id ON visitors(user_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitors_user_id ON visitors(user_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_dead_letter_category ON dead_letter_queue(category)
            """)

            # Site branding/settings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS site_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information"""
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
                        'points': row[4],
                        'created_at': row[5],
                        'updated_at': row[6]
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
        """Create new user"""
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
        points: Optional[int] = None
    ) -> bool:
        """Update user information"""
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
        """Update user's last activity timestamp"""
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
    
    async def record_download(
        self,
        user_id: int,
        platform: str,
        title: str = None,
        file_size: int = 0,
        file_path: str = None
    ) -> bool:
        """Record a download in the database and update user stats"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create downloads table if not exists
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
                
                # Add total_downloads column to users if not exists
                try:
                    await db.execute("ALTER TABLE users ADD COLUMN total_downloads INTEGER DEFAULT 0")
                except:
                    pass  # Column already exists
                
                # Record the download
                await db.execute("""
                    INSERT INTO downloads (user_id, platform, title, file_size, file_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, platform, title, file_size, file_path))
                
                # Update user total downloads
                await db.execute("""
                    UPDATE users SET total_downloads = COALESCE(total_downloads, 0) + 1
                    WHERE user_id = ?
                """, (user_id,))
                
                # If user doesn't exist, create them
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
        """Get user's download history"""
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
        """Get user's download count for today"""
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
    
    async def track_user_session(self, user_data: dict, activity_type: str = 'message') -> bool:
        """Track user session and activity in real-time"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                user_id = user_data.get('user_id')
                now = datetime.now().isoformat()
                
                # Check if session exists
                async with db.execute(
                    "SELECT user_id, message_count FROM user_sessions WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing session
                    await db.execute("""
                        UPDATE user_sessions 
                        SET last_activity = ?, 
                            activity_type = ?,
                            message_count = message_count + 1,
                            is_active = 1,
                            username = COALESCE(?, username),
                            first_name = COALESCE(?, first_name)
                        WHERE user_id = ?
                    """, (now, activity_type, user_data.get('username'), user_data.get('first_name'), user_id))
                else:
                    # Create new session
                    await db.execute("""
                        INSERT INTO user_sessions 
                        (user_id, username, first_name, last_name, language_code, is_premium, 
                         session_start, last_activity, activity_type, message_count, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
                    """, (
                        user_id,
                        user_data.get('username'),
                        user_data.get('first_name'),
                        user_data.get('last_name'),
                        user_data.get('language_code', 'en'),
                        user_data.get('is_premium', 0),
                        now, now, activity_type
                    ))
                
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error tracking user session: {e}")
            return False
    
    async def get_active_sessions(self, minutes: int = 30) -> list:
        """Get all active user sessions from last X minutes"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                threshold = datetime.now() - timedelta(minutes=minutes)
                
                async with db.execute("""
                    SELECT user_id, username, first_name, last_name, language_code, is_premium,
                           session_start, last_activity, activity_type, message_count, is_active
                    FROM user_sessions
                    WHERE last_activity >= ?
                    ORDER BY last_activity DESC
                """, (threshold.isoformat(),)) as cursor:
                    rows = await cursor.fetchall()
                    
                now = datetime.now()
                sessions = []
                for row in rows:
                    try:
                        last_activity = datetime.fromisoformat(row[7]) if row[7] else now
                        minutes_ago = (now - last_activity).total_seconds() / 60
                        
                        if minutes_ago <= 5:
                            status = 'online'
                        elif minutes_ago <= 15:
                            status = 'active'
                        else:
                            status = 'away'
                    except:
                        status = 'away'
                    
                    sessions.append({
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'language_code': row[4],
                        'is_premium': row[5],
                        'session_start': row[6],
                        'last_activity': row[7],
                        'activity_type': row[8],
                        'message_count': row[9],
                        'is_active': row[10],
                        'status': status
                    })
                
                return sessions
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    async def get_daily_limit(self, user_id: int) -> Optional[Dict]:
        """Get daily download limit for user"""
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
        """Increment daily download count for user"""
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
        """Get user points"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT points FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    
    async def add_user_points(self, user_id: int, points: int) -> bool:
        """Add points to user"""
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
        """Update monthly user visit"""
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
        """Get count of monthly users"""
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
    
    async def get_stats(self) -> Dict:
        """Get download statistics"""
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
                    'total_downloads': 0,
                    'successful_downloads': 0,
                    'failed_downloads': 0,
                    'concurrent_downloads': 0,
                    'average_time': 0.0,
                    'total_wait_time': 0.0,
                    'vip_downloads': 0,
                    'premium_downloads': 0,
                    'free_downloads': 0,
                    'total_users': 0,
                    'monthly_users': 0
                }
    
    async def update_stats(self, stats: Dict):
        """Update download statistics"""
        async with aiosqlite.connect(self.db_path) as db:
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
                    total_downloads = ?,
                    successful_downloads = ?,
                    failed_downloads = ?,
                    concurrent_downloads = ?,
                    average_time = ?,
                    total_wait_time = ?,
                    vip_downloads = ?,
                    premium_downloads = ?,
                    free_downloads = ?,
                    total_users = ?,
                    monthly_users = ?,
                    updated_at = ?
                """,
                (
                    stats['total_downloads'], stats['successful_downloads'], stats['failed_downloads'],
                    stats['concurrent_downloads'], stats['average_time'], stats['total_wait_time'],
                    stats['vip_downloads'], stats['premium_downloads'], stats['free_downloads'],
                    stats['total_users'], stats['monthly_users'], datetime.now().isoformat(),
                    stats['total_downloads'], stats['successful_downloads'], stats['failed_downloads'],
                    stats['concurrent_downloads'], stats['average_time'], stats['total_wait_time'],
                    stats['vip_downloads'], stats['premium_downloads'], stats['free_downloads'],
                    stats['total_users'], stats['monthly_users'], datetime.now().isoformat()
                )
            )
            await db.commit()
    
    async def add_download_task(self, task: Dict) -> bool:
        """Add download task to database"""
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
        """Update download task status"""
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
    
    async def add_to_dead_letter_queue(self, error_entry: Dict) -> bool:
        """Add error entry to dead letter queue"""
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
        """Get entries from dead letter queue"""
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
    
    async def _get_all_users(self, limit: int = 100) -> List[Dict]:
        """Get all users from database (internal use)"""
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
    
    async def cleanup_old_records(self, days: int = 30):
        """Clean up old records"""
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
    
    async def record_visitor(self, visitor_data: Dict) -> bool:
        """Record or update visitor information"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
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
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                        visitor_data.get('username'),
                        visitor_data.get('first_name'),
                        visitor_data.get('last_name'),
                        visitor_data.get('language_code'),
                        visitor_data.get('country'),
                        visitor_data.get('is_bot', 0),
                        visitor_data.get('is_premium', 0),
                        visitor_data.get('added_to_attachment_menu', 0),
                        datetime.now().isoformat()
                    )
                )
                await db.commit()
                logger.info(f"Recorded visitor {visitor_data.get('user_id')}")
                return True
        except Exception as e:
            logger.error(f"Error recording visitor: {e}")
            return False
    
    async def get_visitor(self, user_id: int) -> Optional[Dict]:
        """Get visitor information"""
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
        """Delete a visitor from database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM visitors WHERE user_id = ?", (user_id,))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting visitor {user_id}: {e}")
            return False

    async def get_all_visitors(self, limit: int = 100) -> List[Dict]:
        """Get all visitors from database"""
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
        """Get visitors statistics"""
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
                'total_visitors': 0,
                'total_visits': 0,
                'unique_countries': 0,
                'premium_users': 0,
                'bot_count': 0
            }
    
    async def backup_database(self, backup_path: str) -> bool:
        """Create backup of database"""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            return False

    # ─── Activation Keys Management ───────────────────────────────────────

    async def create_activation_key(
        self,
        key: str,
        owner_name: str = "",
        usage_limit: int = 10,
        notes: str = "",
        platform: str = ""
    ) -> bool:
        """Create a new activation key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO activation_keys (key, owner_name, usage_limit, notes, platform)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, owner_name, usage_limit, notes, platform)
                )
                await db.commit()
                logger.info(f"Created {platform or 'generic'} activation key for {owner_name}")
                return True
        except Exception as e:
            logger.error(f"Error creating activation key: {e}")
            return False

    async def validate_activation_key(self, key: str, platform: str = "") -> dict:
        """Validate an activation key and return its status.
        Args: 
            key: the activation key
            platform: optional platform check (e.g. 'TikTok', 'Snapchat')
        Returns dict with: valid(bool), message(str), usage_left(int or None)
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT key, owner_name, usage_limit, usage_count, is_active, notes, COALESCE(platform, '') FROM activation_keys WHERE key = ?",
                    (key,)
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    return {"valid": False, "message": "مفتاح التفعيل غير صالح", "usage_left": None}

                if not row[4]:  # is_active
                    return {"valid": False, "message": "تم تعطيل هذا المفتاح", "usage_left": None}

                key_platform = row[6] or ""
                if platform and key_platform and key_platform != platform:
                    return {"valid": False, "message": f"هذا المفتاح خاص بمنصة {key_platform} وليس {platform}", "usage_left": None}

                usage_left = row[2] - row[3]
                if usage_left <= 0:
                    return {"valid": False, "message": "تم استهلاك حد الاستخدام لهذا المفتاح", "usage_left": 0}

                return {
                    "valid": True,
                    "message": "مفتاح صالح",
                    "usage_left": usage_left,
                    "owner_name": row[1],
                    "usage_limit": row[2],
                    "usage_count": row[3],
                    "platform": key_platform
                }
        except Exception as e:
            logger.error(f"Error validating activation key: {e}")
            return {"valid": False, "message": "حدث خطأ أثناء التحقق من المفتاح", "usage_left": None}

    async def consume_activation_key(self, key: str) -> bool:
        """Increment usage count for an activation key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    UPDATE activation_keys
                    SET usage_count = usage_count + 1, last_used_at = ?
                    WHERE key = ? AND is_active = 1 AND usage_count < usage_limit
                    """,
                    (datetime.now().isoformat(), key)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error consuming activation key: {e}")
            return False

    async def get_all_activation_keys(self) -> list:
        """Get all activation keys"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT key, owner_name, usage_limit, usage_count, is_active, created_at, last_used_at, notes, COALESCE(platform, '') FROM activation_keys ORDER BY created_at DESC"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            "key": row[0],
                            "owner_name": row[1],
                            "usage_limit": row[2],
                            "usage_count": row[3],
                            "is_active": bool(row[4]),
                            "created_at": row[5],
                            "last_used_at": row[6],
                            "notes": row[7],
                            "platform": row[8]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting activation keys: {e}")
            return []

    async def toggle_activation_key(self, key: str, active: bool) -> bool:
        """Enable or disable an activation key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE activation_keys SET is_active = ? WHERE key = ?",
                    (1 if active else 0, key)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error toggling activation key: {e}")
            return False

    async def update_activation_key_limit(self, key: str, limit: int) -> bool:
        """Update usage limit for an activation key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE activation_keys SET usage_limit = ? WHERE key = ?",
                    (limit, key)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating key limit: {e}")
            return False

    async def update_activation_key_count(self, key: str, count: int) -> bool:
        """Update usage count for an activation key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE activation_keys SET usage_count = ? WHERE key = ?",
                    (count, key)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating key count: {e}")
            return False

    async def update_activation_key(self, key: str, usage_count: int = None, usage_limit: int = None) -> bool:
        """Update usage count and/or limit for an activation key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if usage_count is not None:
                    await db.execute("UPDATE activation_keys SET usage_count = ? WHERE key = ?", (usage_count, key))
                if usage_limit is not None:
                    await db.execute("UPDATE activation_keys SET usage_limit = ? WHERE key = ?", (usage_limit, key))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating key: {e}")
            return False

    async def delete_activation_key(self, key: str) -> bool:
        """Delete an activation key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM activation_keys WHERE key = ?",
                    (key,)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting activation key: {e}")
            return False

    async def find_keys_by_owner(self, owner_name: str) -> list:
        """Find all activation keys belonging to an owner (email)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT key, owner_name, usage_limit, usage_count, is_active, created_at, notes FROM activation_keys WHERE owner_name = ? ORDER BY created_at DESC",
                    (owner_name,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            "key": row[0],
                            "owner_name": row[1],
                            "usage_limit": row[2],
                            "usage_count": row[3],
                            "is_active": bool(row[4]),
                            "created_at": row[5],
                            "notes": row[6]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error finding keys by owner: {e}")
            return []

    async def create_subscription_request(self, email: str, name: str = "") -> bool:
        """Record a subscription request"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS subscription_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'new'
                    )
                """)
                await db.execute(
                    "INSERT INTO subscription_requests (email, name) VALUES (?, ?)",
                    (email, name)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating subscription request: {e}")
            return False

    # ─── Web Visitors Tracking ──────────────────────────────────────────

    async def record_web_visitor(self, visitor: dict) -> bool:
        """Record a web visitor visit"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS web_visitors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT,
                        country TEXT DEFAULT 'unknown',
                        country_code TEXT DEFAULT '??',
                        user_agent TEXT,
                        device_type TEXT DEFAULT 'desktop',
                        browser TEXT,
                        os TEXT,
                        page TEXT,
                        visit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.execute("""
                    INSERT INTO web_visitors (ip, country, country_code, user_agent, device_type, browser, os, page)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    visitor.get('ip', 'unknown'),
                    visitor.get('country', 'unknown'),
                    visitor.get('country_code', '??'),
                    visitor.get('user_agent', '')[:200],
                    visitor.get('device_type', 'desktop'),
                    visitor.get('browser', '')[:50],
                    visitor.get('os', '')[:50],
                    visitor.get('page', '/')[:100]
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error recording web visitor: {e}")
            return False

    async def get_web_visitor_stats(self) -> dict:
        """Get web visitor statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}

                async with db.execute("SELECT COUNT(*) FROM web_visitors") as c:
                    stats["total_visits"] = (await c.fetchone())[0] or 0

                async with db.execute(
                    "SELECT COUNT(DISTINCT ip) FROM web_visitors"
                ) as c:
                    stats["unique_visitors"] = (await c.fetchone())[0] or 0

                async with db.execute(
                    "SELECT COUNT(DISTINCT ip) FROM web_visitors WHERE visit_time >= datetime('now', '-24 hours')"
                ) as c:
                    stats["today_visitors"] = (await c.fetchone())[0] or 0

                async with db.execute(
                    "SELECT device_type, COUNT(*) as cnt FROM web_visitors GROUP BY device_type ORDER BY cnt DESC"
                ) as c:
                    stats["device_breakdown"] = {row[0]: row[1] for row in await c.fetchall()}

                async with db.execute(
                    "SELECT browser, COUNT(*) as cnt FROM web_visitors GROUP BY browser ORDER BY cnt DESC LIMIT 5"
                ) as c:
                    stats["browser_breakdown"] = {row[0]: row[1] for row in await c.fetchall()}

                async with db.execute(
                    "SELECT country, country_code, COUNT(*) as cnt FROM web_visitors GROUP BY country ORDER BY cnt DESC"
                ) as c:
                    stats["country_breakdown"] = [
                        {"country": row[0], "code": row[1], "count": row[2]}
                        for row in await c.fetchall()
                    ]

                return stats
        except Exception as e:
            logger.error(f"Error getting web visitor stats: {e}")
            return {}

    async def get_recent_web_visitors(self, limit: int = 20) -> list:
        """Get most recent web visitors"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT ip, country, country_code, device_type, browser, os, page, visit_time FROM web_visitors ORDER BY visit_time DESC LIMIT ?",
                    (limit,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            "ip": r[0], "country": r[1], "country_code": r[2],
                            "device_type": r[3], "browser": r[4], "os": r[5],
                            "page": r[6], "visit_time": r[7]
                        }
                        for r in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting recent visitors: {e}")
            return []

    # ─── Admin Auth ────────────────────────────────────────────────────

    async def verify_admin_password(self, password: str) -> bool:
        """Verify admin password against stored hash"""
        import hashlib
        import os as _os
        from dotenv import load_dotenv
        load_dotenv()
        admin_hash = _os.getenv("ADMIN_PASSWORD_HASH", "")
        if not admin_hash:
            return False
        pwhash = hashlib.sha256(password.encode()).hexdigest()
        return pwhash == admin_hash

    async def create_admin_session(self, token: str) -> bool:
        """Store a new admin session"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS admin_sessions (
                        token TEXT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP
                    )
                """)
                expiry = (datetime.now() + timedelta(days=7)).isoformat()
                await db.execute(
                    "INSERT INTO admin_sessions (token, created_at, expires_at) VALUES (?, ?, ?)",
                    (token, datetime.now().isoformat(), expiry)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating admin session: {e}")
            return False

    async def validate_admin_session(self, token: str) -> bool:
        """Check if an admin session token is valid"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM admin_sessions WHERE datetime(expires_at) < datetime('now')"
                )
                await db.commit()
                async with db.execute(
                    "SELECT token FROM admin_sessions WHERE token = ?",
                    (token,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return bool(row)
        except Exception as e:
            logger.error(f"Error validating admin session: {e}")
            return False

    async def delete_admin_session(self, token: str) -> bool:
        """Delete an admin session (logout)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False

    async def get_subscription_requests(self, status: str = "new") -> list:
        """Get subscription requests"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, email, name, created_at, status FROM subscription_requests WHERE status = ? ORDER BY created_at DESC LIMIT 50",
                    (status,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {"id": r[0], "email": r[1], "name": r[2], "created_at": r[3], "status": r[4]}
                        for r in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting subscription requests: {e}")
            return []

    async def update_subscription_status(self, req_id: int, new_status: str) -> bool:
        """Update subscription request status"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE subscription_requests SET status = ? WHERE id = ?",
                    (new_status, req_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            return False

    async def get_admin_stats(self) -> dict:
        """Get comprehensive admin statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}

                async with db.execute("SELECT COUNT(*) FROM activation_keys") as c:
                    stats["total_keys"] = (await c.fetchone())[0]

                async with db.execute("SELECT COUNT(*) FROM activation_keys WHERE is_active = 1") as c:
                    stats["active_keys"] = (await c.fetchone())[0]

                async with db.execute("SELECT SUM(usage_count) FROM activation_keys") as c:
                    stats["total_usage"] = (await c.fetchone())[0] or 0

                async with db.execute("SELECT COUNT(*) FROM device_keys") as c:
                    stats["device_keys"] = (await c.fetchone())[0]

                async with db.execute("SELECT COUNT(*) FROM subscription_requests WHERE status = 'new'") as c:
                    stats["pending_requests"] = (await c.fetchone())[0]

                try:
                    async with db.execute("SELECT COUNT(*) FROM downloads") as c:
                        stats["total_downloads"] = (await c.fetchone())[0]
                except:
                    stats["total_downloads"] = 0

                return stats
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            return {}

    # ─── Device Keys (auto-generated free keys with daily reset) ──────

    async def get_or_create_device_key(self, device_id: str, daily_limit: int = 5, platform: str = "") -> dict:
        """Get existing device key or create a new one. Usage count resets every 24 hours."""
        import secrets
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.now()
                async with db.execute(
                    "SELECT key, daily_limit, daily_count, last_reset FROM device_keys WHERE device_id = ?",
                    (device_id,)
                ) as cursor:
                    row = await cursor.fetchone()

                if row:
                    key = row[0]
                    daily_limit_db = row[1]
                    # Sync daily_limit if changed from config
                    if daily_limit_db != daily_limit:
                        await db.execute("UPDATE device_keys SET daily_limit = ? WHERE device_id = ?", (daily_limit, device_id))
                        await db.execute("UPDATE activation_keys SET usage_limit = ? WHERE key = ?", (daily_limit, key))
                        await db.commit()
                        daily_limit_db = daily_limit
                    daily_count = row[2]
                    last_reset_raw = row[3]
                    last_reset = datetime.fromisoformat(last_reset_raw) if last_reset_raw else None

                    # Check if we've passed the reset hour since last reset
                    should_reset = False
                    if last_reset:
                        try:
                            from web.app import get_reset_hour
                            rh = get_reset_hour()
                            next_reset = last_reset.replace(hour=rh, minute=0, second=0, microsecond=0)
                            if next_reset <= last_reset:
                                next_reset += timedelta(days=1)
                            if now >= next_reset:
                                should_reset = True
                        except:
                            if (now - last_reset).total_seconds() >= 86400:
                                should_reset = True
                    if should_reset:
                        await db.execute(
                            "UPDATE device_keys SET daily_count = 0, last_reset = ? WHERE device_id = ?",
                            (now.isoformat(), device_id)
                        )
                        await db.execute(
                            "UPDATE activation_keys SET usage_count = 0 WHERE key = ?",
                            (key,)
                        )
                        await db.commit()
                        daily_count = 0
                        last_reset = now

                    if daily_count >= daily_limit_db:
                        if last_reset:
                            reset_at = last_reset + timedelta(hours=24)
                            remaining = str(reset_at - now).split('.')[0]
                        else:
                            remaining = "?"
                        return {
                            "success": False,
                            "message": f"استهلكت حد الـ {daily_limit_db} تحميلات اليومية. تعود بعد {remaining}",
                            "key": key,
                            "usage_left": 0,
                            "usage_limit": daily_limit_db
                        }

                    return {
                        "success": True,
                        "key": key,
                        "usage_left": daily_limit_db - daily_count,
                        "usage_limit": daily_limit_db,
                        "resets_in": str(last_reset + timedelta(hours=24) - now).split('.')[0] if last_reset else "?"
                    }

                # Create new key with platform-specific prefix
                KEY_PREFIXES = {"TikTok": "ttk-", "Snapchat": "sc-"}
                prefix = KEY_PREFIXES.get(platform, "k-")
                new_key = prefix + secrets.token_hex(4)

                await db.execute(
                    "INSERT INTO device_keys (device_id, key, daily_limit, daily_count, last_reset) VALUES (?, ?, ?, 0, ?)",
                    (device_id, new_key, daily_limit, now.isoformat())
                )
                await db.execute(
                    "INSERT OR IGNORE INTO activation_keys (key, owner_name, usage_limit, usage_count, is_active, notes, platform) VALUES (?, ?, ?, 0, 1, ?, ?)",
                    (new_key, f"device:{device_id[:20]}", daily_limit, f"مفتاح مجاني - {daily_limit} تحميلات يومياً", platform)
                )
                await db.commit()

                return {
                    "success": True,
                    "key": new_key,
                    "usage_left": daily_limit,
                    "usage_limit": daily_limit,
                    "resets_in": "24:00:00"
                }
        except Exception as e:
            logger.error(f"Error managing device key: {e}")
            return {"success": False, "message": "حدث خطأ أثناء إنشاء المفتاح"}

    # ─── Site Settings / Branding ───────────────────────────────────────

    async def get_site_setting(self, key: str, default: str = "") -> str:
        """Get a single site setting value"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT value FROM site_settings WHERE key = ?", (key,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row and row[0] is not None else default
        except Exception as e:
            logger.error(f"Error getting site setting {key}: {e}")
            return default

    async def set_site_setting(self, key: str, value: str) -> bool:
        """Set or update a site setting"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO site_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                """, (key, value, datetime.now().isoformat()))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting site setting {key}: {e}")
            return False

    async def get_all_site_settings(self) -> dict:
        """Get all site settings as a dict"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT key, value FROM site_settings") as cursor:
                    rows = await cursor.fetchall()
                    return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.error(f"Error getting all site settings: {e}")
            return {}

    async def consume_device_key(self, device_id: str, key: str) -> bool:
        """Increment daily usage count for device key (device_keys table only)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    UPDATE device_keys SET daily_count = daily_count + 1
                    WHERE device_id = ? AND key = ? AND daily_count < daily_limit
                    """,
                    (device_id, key)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error consuming device key: {e}")
            return False

    # ─── Dashboard & Advanced Stats ─────────────────────────────────────

    async def get_dashboard_stats(self) -> dict:
        """Get combined dashboard statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Total keys
                async with db.execute("SELECT COUNT(*) FROM activation_keys WHERE is_active=1") as c:
                    active_keys = (await c.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM activation_keys") as c:
                    total_keys = (await c.fetchone())[0]

                # Downloads today
                today = datetime.now().strftime('%Y-%m-%d')
                async with db.execute(
                    "SELECT COUNT(*) FROM downloads WHERE date(downloaded_at)=date(?)", (today,)
                ) as c:
                    downloads_today = (await c.fetchone())[0]

                # Total downloads
                async with db.execute("SELECT COUNT(*) FROM downloads") as c:
                    total_downloads = (await c.fetchone())[0]

                # Platform breakdown
                async with db.execute(
                    "SELECT platform, COUNT(*) FROM downloads GROUP BY platform ORDER BY COUNT(*) DESC"
                ) as c:
                    platform_stats = [{"platform": r[0], "count": r[1]} for r in await c.fetchall()]

                # Pending subs
                async with db.execute("SELECT COUNT(*) FROM subscription_requests WHERE status='new'") as c:
                    pending_subs = (await c.fetchone())[0]

                # Unique visitors today
                async with db.execute(
                    "SELECT COUNT(DISTINCT ip) FROM web_visitors WHERE date(visit_time)=date(?)", (today,)
                ) as c:
                    visitors_today = (await c.fetchone())[0]

                return {
                    "active_keys": active_keys or 0,
                    "total_keys": total_keys or 0,
                    "downloads_today": downloads_today or 0,
                    "total_downloads": total_downloads or 0,
                    "platform_stats": platform_stats,
                    "pending_subs": pending_subs or 0,
                    "visitors_today": visitors_today or 0,
                }
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}

    async def get_download_logs(self, page: int = 1, per_page: int = 50, platform: str = "") -> dict:
        """Get paginated download history"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                offset = (page - 1) * per_page
                where = f"WHERE d.platform = ?" if platform else ""
                params = [platform] if platform else []

                count_q = f"SELECT COUNT(*) FROM downloads d {where}"
                async with db.execute(count_q, params) as c:
                    total = (await c.fetchone())[0]

                query = f"""
                    SELECT d.id, d.user_id, d.platform, d.title, d.file_size, d.downloaded_at
                    FROM downloads d {where}
                    ORDER BY d.downloaded_at DESC LIMIT ? OFFSET ?
                """
                async with db.execute(query, params + [per_page, offset]) as c:
                    rows = await c.fetchall()
                    logs = [{
                        "id": r[0], "user_id": r[1], "platform": r[2],
                        "title": r[3] or "-", "file_size": r[4] or 0,
                        "downloaded_at": r[5]
                    } for r in rows]

                return {"logs": logs, "total": total, "page": page, "per_page": per_page,
                        "total_pages": max(1, (total + per_page - 1) // per_page)}
        except Exception as e:
            logger.error(f"Error getting download logs: {e}")
            return {"logs": [], "total": 0, "page": 1, "per_page": per_page, "total_pages": 1}

    async def get_download_trends(self, days: int = 14) -> list:
        """Get daily download counts per platform for chart"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                async with db.execute(
                    """SELECT date(downloaded_at) as d, platform, COUNT(*) 
                       FROM downloads WHERE date(downloaded_at) >= ?
                       GROUP BY d, platform ORDER BY d ASC""", (since,)
                ) as c:
                    rows = await c.fetchall()
                    return [{"date": r[0], "platform": r[1], "count": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"Error getting trends: {e}")
            return []

    async def search_keys(self, query: str = "", platform: str = "") -> list:
        """Search/filter activation keys"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                sql = "SELECT key, owner_name, usage_limit, usage_count, is_active, created_at, last_used_at, notes, COALESCE(platform,'') FROM activation_keys WHERE 1=1"
                params = []
                if query:
                    sql += " AND (key LIKE ? OR owner_name LIKE ? OR notes LIKE ?)"
                    q = f"%{query}%"
                    params.extend([q, q, q])
                if platform:
                    sql += " AND platform = ?"
                    params.append(platform)
                sql += " ORDER BY created_at DESC LIMIT 200"
                async with db.execute(sql, params) as c:
                    rows = await c.fetchall()
                    return [{
                        "key": r[0], "owner_name": r[1] or "-",
                        "usage_limit": r[2], "usage_count": r[3],
                        "is_active": bool(r[4]), "created_at": r[5],
                        "last_used_at": r[6], "notes": r[7] or "-",
                        "platform": r[8] or "-"
                    } for r in rows]
        except Exception as e:
            logger.error(f"Error searching keys: {e}")
            return []

    async def export_keys_csv(self) -> str:
        """Export all keys as CSV string"""
        try:
            keys = await self.get_all_activation_keys()
            lines = ["key,owner_name,platform,usage_count,usage_limit,is_active,created_at,notes"]
            for k in keys:
                lines.append(f'{k["key"]},{k["owner_name"]},{k.get("platform","")},{k["usage_count"]},{k["usage_limit"]},{k["is_active"]},{k["created_at"]},{k.get("notes","")}')
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error exporting keys: {e}")
            return ""

    # ─── Web Rewards / Points ──────────────────────────────────────

    async def _ensure_web_rewards_table(self, db):
        await db.execute("""
            CREATE TABLE IF NOT EXISTS web_rewards (
                email TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                last_visit_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reward_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                points_awarded INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def create_reward_token(self, email: str, points: int = 5) -> str:
        """Create a reward visit token for a user"""
        import secrets
        try:
            token = secrets.token_hex(8)
            async with aiosqlite.connect(self.db_path) as db:
                await self._ensure_web_rewards_table(db)
                await db.execute(
                    "INSERT INTO reward_visits (email, token, points_awarded) VALUES (?, ?, ?)",
                    (email, token, points)
                )
                await db.commit()
                return token
        except Exception as e:
            logger.error(f"Error creating reward token: {e}")
            return ""

    async def claim_reward_visit(self, email: str, token: str) -> dict:
        """Claim reward points from a visit token"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await self._ensure_web_rewards_table(db)
                async with db.execute(
                    "SELECT id, points_awarded, claimed FROM reward_visits WHERE token = ? AND email = ?",
                    (token, email)
                ) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    return {"success": False, "message": "رمز غير صالح"}
                vid, points, claimed = row
                if claimed:
                    return {"success": False, "message": "تم استلام المكافأة مسبقاً"}

                # Check daily limits
                today = datetime.now().strftime('%Y-%m-%d')
                async with db.execute(
                    "SELECT COUNT(*), COALESCE(SUM(points_awarded),0) FROM reward_visits WHERE email = ? AND claimed = 1 AND date(created_at) = ?",
                    (email, today)
                ) as cursor:
                    row2 = await cursor.fetchone()
                daily_visits = row2[0] if row2 else 0
                daily_points = row2[1] if row2 else 0
                MAX_VISITS_PER_DAY = 5
                MAX_POINTS_PER_DAY = 25
                if daily_visits >= MAX_VISITS_PER_DAY:
                    return {"success": False, "message": f"وصلت للحد اليومي ({MAX_VISITS_PER_DAY} زيارات). حاول غداً"}
                if daily_points + points > MAX_POINTS_PER_DAY:
                    return {"success": False, "message": f"وصلت للحد اليومي من النقاط ({MAX_POINTS_PER_DAY} نقطة). حاول غداً"}

                # Check cooldown (15 min between claims)
                async with db.execute(
                    "SELECT created_at FROM reward_visits WHERE email = ? AND claimed = 1 ORDER BY created_at DESC LIMIT 1",
                    (email,)
                ) as cursor:
                    row3 = await cursor.fetchone()
                if row3:
                    last_claim = datetime.fromisoformat(row3[0])
                    cooldown_seconds = (datetime.now() - last_claim).total_seconds()
                    if cooldown_seconds < 900:
                        mins_left = int((900 - cooldown_seconds) / 60) + 1
                        return {"success": False, "message": f"يرجى الانتظار {mins_left} دقيقة بين الزيارات"}

                await db.execute("UPDATE reward_visits SET claimed = 1 WHERE id = ?", (vid,))
                await db.execute(
                    """INSERT OR IGNORE INTO web_rewards (email, points, total_earned) VALUES (?, ?, ?)""",
                    (email, 0, 0)
                )
                await db.execute(
                    """UPDATE web_rewards SET points = points + ?, total_earned = total_earned + ?, last_visit_at = ? WHERE email = ?""",
                    (points, points, datetime.now().isoformat(), email)
                )
                await db.commit()
                remaining = MAX_POINTS_PER_DAY - daily_points - points
                return {"success": True, "points_earned": points, "message": f"تم إضافة {points} نقاط", "daily_remaining": remaining, "daily_visits_left": MAX_VISITS_PER_DAY - daily_visits - 1}
        except Exception as e:
            logger.error(f"Error claiming reward: {e}")
            return {"success": False, "message": "حدث خطأ"}

    async def get_web_points(self, email: str) -> dict:
        """Get web user points balance with daily stats"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await self._ensure_web_rewards_table(db)
                async with db.execute(
                    "SELECT points, total_earned, last_visit_at FROM web_rewards WHERE email = ?",
                    (email,)
                ) as cursor:
                    row = await cursor.fetchone()
                today = datetime.now().strftime('%Y-%m-%d')
                async with db.execute(
                    "SELECT COUNT(*), COALESCE(SUM(points_awarded),0) FROM reward_visits WHERE email = ? AND claimed = 1 AND date(created_at) = ?",
                    (email, today)
                ) as cursor:
                    row2 = await cursor.fetchone()
                daily_visits = row2[0] if row2 else 0
                daily_points = row2[1] if row2 else 0
                MAX_VISITS = 5
                MAX_POINTS = 25
                if row:
                    return {"points": row[0], "total_earned": row[1], "last_visit_at": row[2],
                            "daily_visits": daily_visits, "daily_points": daily_points,
                            "daily_visits_max": MAX_VISITS, "daily_points_max": MAX_POINTS}
                return {"points": 0, "total_earned": 0, "last_visit_at": None,
                        "daily_visits": daily_visits, "daily_points": daily_points,
                        "daily_visits_max": MAX_VISITS, "daily_points_max": MAX_POINTS}
        except Exception as e:
            logger.error(f"Error getting web points: {e}")
            return {"points": 0, "total_earned": 0, "last_visit_at": None,
                    "daily_visits": 0, "daily_points": 0,
                    "daily_visits_max": 5, "daily_points_max": 25}

    async def redeem_web_points(self, email: str, points: int, key_value: str) -> dict:
        """Redeem points for extra downloads on a key"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await self._ensure_web_rewards_table(db)
                async with db.execute(
                    "SELECT points FROM web_rewards WHERE email = ?", (email,)
                ) as cursor:
                    row = await cursor.fetchone()
                if not row or row[0] < points:
                    return {"success": False, "message": "نقاط غير كافية"}
                async with db.execute(
                    "SELECT usage_limit, usage_count, is_active FROM activation_keys WHERE key = ? AND owner_name = ?",
                    (key_value, email)
                ) as cursor:
                    krow = await cursor.fetchone()
                if not krow:
                    return {"success": False, "message": "المفتاح غير موجود"}
                if not krow[2]:
                    return {"success": False, "message": "المفتاح غير مفعل"}
                extra_downloads = points // 10
                if extra_downloads < 1:
                    return {"success": False, "message": "تحتاج 10 نقاط على الأقل"}
                await db.execute(
                    "UPDATE activation_keys SET usage_limit = usage_limit + ? WHERE key = ?",
                    (extra_downloads, key_value)
                )
                await db.execute(
                    "UPDATE web_rewards SET points = points - ? WHERE email = ?",
                    (extra_downloads * 10, email)
                )
                await db.commit()
                return {"success": True, "downloads_added": extra_downloads, "message": f"تم إضافة {extra_downloads} تحميلات"}
        except Exception as e:
            logger.error(f"Error redeeming points: {e}")
            return {"success": False, "message": "حدث خطأ"}

    # ─── Landing Page Settings ────────────────────────────────────────

    async def get_landing_page_settings(self) -> dict:
        """Get landing page (istx.io) specific settings"""
        settings = await self.get_all_site_settings()
        landing = {}
        for k, v in settings.items():
            if k.startswith("landing:"):
                landing[k[8:]] = v
        return landing

    async def set_landing_page_setting(self, key: str, value: str) -> bool:
        return await self.set_site_setting(f"landing:{key}", value)


_global_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance"""
    global _global_db_manager
    if _global_db_manager is None:
        _global_db_manager = DatabaseManager()
    return _global_db_manager


async def init_database(db_path: str = "bot_data.db") -> DatabaseManager:
    """Initialize global database manager"""
    global _global_db_manager
    _global_db_manager = DatabaseManager(db_path)
    await _global_db_manager.initialize()
    return _global_db_manager
