import sqlite3
import aiosqlite
import logging
import json
from datetime import datetime
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
    
    # ============= OTP Authentication System =============
    
    async def create_otp(self, user_id: int) -> str:
        """Generate and store OTP for user authentication"""
        import random
        import string
        
        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        expires_at = datetime.now().timestamp() + 300  # 5 minutes expiry
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create OTP table if not exists
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS otp_codes (
                        user_id INTEGER PRIMARY KEY,
                        otp_code TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at REAL NOT NULL,
                        attempts INTEGER DEFAULT 0,
                        verified BOOLEAN DEFAULT 0
                    )
                """)
                
                # Delete any existing OTP for this user
                await db.execute("DELETE FROM otp_codes WHERE user_id = ?", (user_id,))
                
                # Insert new OTP
                await db.execute("""
                    INSERT INTO otp_codes (user_id, otp_code, expires_at)
                    VALUES (?, ?, ?)
                """, (user_id, otp, expires_at))
                
                await db.commit()
                logger.info(f"Created OTP for user {user_id}")
                return otp
        except Exception as e:
            logger.error(f"Error creating OTP: {e}")
            return None
    
    async def verify_otp(self, user_id: int, otp_code: str) -> dict:
        """Verify OTP code and return result"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT otp_code, expires_at, attempts, verified FROM otp_codes 
                    WHERE user_id = ?
                """, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                
                if not row:
                    return {'success': False, 'error': 'لم يتم العثور على رمز تحقق. اطلب رمزاً جديداً.'}
                
                # Check if already verified
                if row['verified']:
                    return {'success': False, 'error': 'تم استخدام هذا الرمز مسبقاً.'}
                
                # Check expiry
                if datetime.now().timestamp() > row['expires_at']:
                    return {'success': False, 'error': 'انتهت صلاحية الرمز. اطلب رمزاً جديداً.'}
                
                # Check attempts (max 3)
                if row['attempts'] >= 3:
                    return {'success': False, 'error': 'تجاوزت عدد المحاولات المسموحة. اطلب رمزاً جديداً.'}
                
                # Verify OTP
                if row['otp_code'] != otp_code:
                    # Increment attempts
                    await db.execute("""
                        UPDATE otp_codes SET attempts = attempts + 1 WHERE user_id = ?
                    """, (user_id,))
                    await db.commit()
                    remaining = 3 - (row['attempts'] + 1)
                    return {
                        'success': False, 
                        'error': f'رمز غير صحيح. المتبقي: {remaining} محاولات'
                    }
                
                # Success - mark as verified
                await db.execute("""
                    UPDATE otp_codes SET verified = 1 WHERE user_id = ?
                """, (user_id,))
                await db.commit()
                
                return {'success': True, 'message': 'تم التحقق بنجاح'}
                
        except Exception as e:
            logger.error(f"Error verifying OTP: {e}")
            return {'success': False, 'error': 'حدث خطأ أثناء التحقق'}
    
    async def create_session(self, user_id: int, ip_address: str = None) -> str:
        """Create authenticated session for user"""
        import secrets
        
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now().timestamp() + 86400  # 24 hours
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create sessions table if not exists
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS web_sessions (
                        session_token TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        ip_address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at REAL NOT NULL,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Delete old sessions for this user
                await db.execute("DELETE FROM web_sessions WHERE user_id = ?", (user_id,))
                
                # Create new session
                await db.execute("""
                    INSERT INTO web_sessions (session_token, user_id, ip_address, expires_at)
                    VALUES (?, ?, ?, ?)
                """, (session_token, user_id, ip_address, expires_at))
                
                await db.commit()
                return session_token
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    async def verify_session(self, session_token: str) -> dict:
        """Verify session token and return user data"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT s.user_id, s.expires_at, s.last_activity, 
                           u.username, u.first_name, u.tier, u.points, u.total_downloads
                    FROM web_sessions s
                    LEFT JOIN users u ON s.user_id = u.user_id
                    WHERE s.session_token = ?
                """, (session_token,)) as cursor:
                    row = await cursor.fetchone()
                
                if not row:
                    return {'valid': False, 'error': 'جلسة غير صالحة'}
                
                # Check expiry
                if datetime.now().timestamp() > row['expires_at']:
                    return {'valid': False, 'error': 'انتهت صلاحية الجلسة'}
                
                # Update last activity
                await db.execute("""
                    UPDATE web_sessions SET last_activity = ? WHERE session_token = ?
                """, (datetime.now().isoformat(), session_token))
                await db.commit()
                
                return {
                    'valid': True,
                    'user_id': row['user_id'],
                    'username': row['username'] or row['first_name'],
                    'tier': row['tier'] or 'free',
                    'points': row['points'] or 0,
                    'total_downloads': row['total_downloads'] or 0
                }
        except Exception as e:
            logger.error(f"Error verifying session: {e}")
            return {'valid': False, 'error': 'حدث خطأ'}
    
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
