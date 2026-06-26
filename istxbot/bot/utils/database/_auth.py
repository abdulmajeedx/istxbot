"""
نظام المصادقة — OTP، الجلسات، وتتبع النشاط الفوري
"""
import aiosqlite
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class AuthMixin:
    """خلط عمليات المصادقة والجلسات"""

    # ═══ OTP Authentication System ═══

    async def create_otp(self, user_id: int) -> str:
        """توليد وتخزين رمز تحقق OTP للمستخدم"""
        import random
        import string

        # توليد OTP من 6 أرقام
        otp = ''.join(random.choices(string.digits, k=6))
        expires_at = datetime.now().timestamp() + 300  # صلاحية 5 دقائق

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # إنشاء جدول OTP إذا لم يكن موجوداً
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

                # حذف أي OTP سابق للمستخدم
                await db.execute("DELETE FROM otp_codes WHERE user_id = ?", (user_id,))

                # إدخال OTP جديد
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
        """التحقق من صحة رمز OTP"""
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

                # التأكد من عدم استخدام الرمز مسبقاً
                if row['verified']:
                    return {'success': False, 'error': 'تم استخدام هذا الرمز مسبقاً.'}

                # التحقق من الصلاحية
                if datetime.now().timestamp() > row['expires_at']:
                    return {'success': False, 'error': 'انتهت صلاحية الرمز. اطلب رمزاً جديداً.'}

                # التحقق من عدد المحاولات (الحد الأقصى 3)
                if row['attempts'] >= 3:
                    return {'success': False, 'error': 'تجاوزت عدد المحاولات المسموحة. اطلب رمزاً جديداً.'}

                # التحقق من OTP
                if row['otp_code'] != otp_code:
                    await db.execute(
                        "UPDATE otp_codes SET attempts = attempts + 1 WHERE user_id = ?",
                        (user_id,)
                    )
                    await db.commit()
                    remaining = 3 - (row['attempts'] + 1)
                    return {
                        'success': False,
                        'error': f'رمز غير صحيح. المتبقي: {remaining} محاولات'
                    }

                # نجاح التحقق - تعليم الرمز كمستخدم
                await db.execute(
                    "UPDATE otp_codes SET verified = 1 WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()

                return {'success': True, 'message': 'تم التحقق بنجاح'}

        except Exception as e:
            logger.error(f"Error verifying OTP: {e}")
            return {'success': False, 'error': 'حدث خطأ أثناء التحقق'}

    # ═══ Web Sessions ═══

    async def create_session(self, user_id: int, ip_address: str = None) -> str:
        """إنشاء جلسة ويب موثقة للمستخدم"""
        import secrets

        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now().timestamp() + 86400  # صلاحية 24 ساعة

        try:
            async with aiosqlite.connect(self.db_path) as db:
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

                # حذف الجلسات القديمة للمستخدم
                await db.execute("DELETE FROM web_sessions WHERE user_id = ?", (user_id,))

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
        """التحقق من صحة رمز الجلسة وإرجاع بيانات المستخدم"""
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

                if datetime.now().timestamp() > row['expires_at']:
                    return {'valid': False, 'error': 'انتهت صلاحية الجلسة'}

                # تحديث آخر نشاط
                await db.execute(
                    "UPDATE web_sessions SET last_activity = ? WHERE session_token = ?",
                    (datetime.now().isoformat(), session_token)
                )
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

    # ═══ Real-time Session Tracking ═══

    async def track_user_session(self, user_data: dict, activity_type: str = 'message') -> bool:
        """تتبع نشاط المستخدم وجلساته في الزمن الفوري"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                user_id = user_data.get('user_id')
                now = datetime.now().isoformat()

                async with db.execute(
                    "SELECT user_id, message_count FROM user_sessions WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    existing = await cursor.fetchone()

                if existing:
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
        """جلب جميع الجلسات النشطة خلال آخر X دقيقة"""
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
                    except Exception:
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


