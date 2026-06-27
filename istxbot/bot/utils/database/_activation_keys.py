"""
مفاتيح التفعيل — إنشاء، تحقق، استهلاك، وبحث
"""
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class ActivationKeysMixin:
    """خلط عمليات مفاتيح التفعيل والاشتراكات"""

    # ═══ مفاتيح التفعيل ═══

    async def create_activation_key(
        self, key: str, owner_name: str = "", usage_limit: int = 10,
        notes: str = "", platform: str = ""
    ) -> bool:
        """إنشاء مفتاح تفعيل جديد"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS activation_keys (
                        key TEXT PRIMARY KEY, owner_name TEXT,
                        usage_limit INTEGER DEFAULT 10, usage_count INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP, notes TEXT, platform TEXT DEFAULT ''
                    )
                """)
                await db.execute(
                    "INSERT OR IGNORE INTO activation_keys (key, owner_name, usage_limit, notes, platform) VALUES (?, ?, ?, ?, ?)",
                    (key, owner_name, usage_limit, notes, platform)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating activation key: {e}")
            return False

    async def validate_activation_key(self, key: str, platform: str = "") -> dict:
        """التحقق من صحة مفتاح التفعيل"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS activation_keys (
                        key TEXT PRIMARY KEY, owner_name TEXT,
                        usage_limit INTEGER DEFAULT 10, usage_count INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP, notes TEXT, platform TEXT DEFAULT ''
                    )
                """)
                await db.commit()
                async with db.execute(
                    "SELECT key, owner_name, usage_limit, usage_count, is_active, notes, COALESCE(platform, '') FROM activation_keys WHERE key = ?",
                    (key,)
                ) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    return {"valid": False, "message": "مفتاح التفعيل غير صالح", "usage_left": None}
                if not row[4]:
                    return {"valid": False, "message": "تم تعطيل هذا المفتاح", "usage_left": None}
                key_platform = row[6] or ""
                if platform and key_platform and key_platform != platform:
                    return {"valid": False, "message": f"هذا المفتاح خاص بمنصة {key_platform} وليس {platform}", "usage_left": None}
                usage_left = row[2] - row[3]
                if usage_left <= 0:
                    return {"valid": False, "message": "تم استنفاذ حد التحميل لهذا المفتاح", "usage_left": 0}
                return {"valid": True, "message": "المفتاح صالح", "usage_left": usage_left, "owner_name": row[1]}
        except Exception as e:
            logger.error(f"Error validating key: {e}")
            return {"valid": False, "message": "حدث خطأ", "usage_left": None}

    async def consume_activation_key(self, key: str) -> bool:
        """استهلاك تحميلة من المفتاح"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE activation_keys SET usage_count = usage_count + 1, last_used_at = ? WHERE key = ? AND is_active = 1 AND usage_count < usage_limit",
                    (datetime.now().isoformat(), key)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error consuming key: {e}")
            return False

    async def get_all_activation_keys(self) -> list:
        """جلب جميع مفاتيح التفعيل"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT key, owner_name, usage_limit, usage_count, is_active, created_at, last_used_at, notes, COALESCE(platform, '') FROM activation_keys ORDER BY created_at DESC"
                ) as cursor:
                    return [{"key": r[0], "owner_name": r[1], "usage_limit": r[2], "usage_count": r[3],
                             "is_active": bool(r[4]), "created_at": r[5], "last_used_at": r[6],
                             "notes": r[7], "platform": r[8]} for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting keys: {e}")
            return []

    async def toggle_activation_key(self, key: str, active: bool) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("UPDATE activation_keys SET is_active = ? WHERE key = ?", (1 if active else 0, key))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error toggling key: {e}")
            return False

    async def delete_activation_key(self, key: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM activation_keys WHERE key = ?", (key,))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting key: {e}")
            return False

    async def update_activation_key(self, key: str, usage_count: int = None, usage_limit: int = None) -> bool:
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

    async def find_keys_by_owner(self, owner_name: str) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT key, owner_name, usage_limit, usage_count, is_active, created_at, notes FROM activation_keys WHERE owner_name = ? ORDER BY created_at DESC",
                    (owner_name,)
                ) as cursor:
                    return [{"key": r[0], "owner_name": r[1], "usage_limit": r[2], "usage_count": r[3],
                             "is_active": bool(r[4]), "created_at": r[5], "notes": r[6]} for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error finding keys: {e}")
            return []

    async def search_keys(self, query: str = "", platform: str = "") -> list:
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
                async with db.execute(sql, params) as cursor:
                    return [{"key": r[0], "owner_name": r[1], "usage_limit": r[2], "usage_count": r[3],
                             "is_active": bool(r[4]), "created_at": r[5], "last_used_at": r[6],
                             "notes": r[7], "platform": r[8]} for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error searching keys: {e}")
            return []

    async def export_keys_csv(self) -> str:
        """تصدير المفاتيح كـ CSV"""
        try:
            keys = await self.get_all_activation_keys()
            csv = "key,owner_name,usage_limit,usage_count,is_active,platform,created_at,notes\n"
            for k in keys:
                csv += f"{k['key']},{k['owner_name']},{k['usage_limit']},{k['usage_count']},{k['is_active']},{k['platform']},{k['created_at']},{k['notes']}\n"
            return csv
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            return ""

    # ═══ الاشتراكات ═══

    async def add_subscription_request(self, name: str, email: str, platform: str = "") -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS subscription_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL,
                        name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'new'
                    )
                """)
                await db.execute("INSERT INTO subscription_requests (email, name) VALUES (?, ?)", (email, name))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding subscription: {e}")
            return False

    async def get_subscription_requests(self, status: str = "new") -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, email, name, created_at, status FROM subscription_requests WHERE status = ? ORDER BY created_at DESC LIMIT 50",
                    (status,)
                ) as cursor:
                    return [{"id": r[0], "email": r[1], "name": r[2], "created_at": r[3], "status": r[4]}
                            for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting subscriptions: {e}")
            return []

    async def update_subscription_status(self, req_id: int, new_status: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("UPDATE subscription_requests SET status = ? WHERE id = ?", (new_status, req_id))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            return False

    # ═══ إحصائيات المشرف ═══

    async def get_admin_stats(self) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                async with db.execute("SELECT COUNT(*) FROM activation_keys") as c:
                    stats["total_keys"] = (await c.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM activation_keys WHERE is_active = 1") as c:
                    stats["active_keys"] = (await c.fetchone())[0]
                async with db.execute("SELECT SUM(usage_count) FROM activation_keys") as c:
                    stats["total_usage"] = (await c.fetchone())[0] or 0
                async with db.execute("SELECT COUNT(*) FROM subscription_requests WHERE status = 'new'") as c:
                    stats["pending_requests"] = (await c.fetchone())[0]
                try:
                    async with db.execute("SELECT COUNT(*) FROM downloads") as c:
                        stats["total_downloads"] = (await c.fetchone())[0]
                except Exception:
                    stats["total_downloads"] = 0
                try:
                    today = datetime.now().strftime('%Y-%m-%d')
                    async with db.execute("SELECT COUNT(*) FROM downloads WHERE date(downloaded_at)=date(?)", (today,)) as c:
                        stats["downloads_today"] = (await c.fetchone())[0]
                except Exception:
                    stats["downloads_today"] = 0
                try:
                    async with db.execute("SELECT COUNT(*) FROM users") as c:
                        stats["total_users"] = (await c.fetchone())[0]
                except Exception:
                    stats["total_users"] = 0
                try:
                    async with db.execute("SELECT COUNT(*) FROM monthly_users WHERE last_visit >= datetime('now','-30 days')") as c:
                        stats["monthly_users"] = (await c.fetchone())[0]
                except Exception:
                    stats["monthly_users"] = 0
                return stats
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            return {}

    async def get_dashboard_stats(self) -> dict:
        stats = await self.get_admin_stats()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(DISTINCT ip) FROM web_visitors WHERE visit_time >= datetime('now','-24 hours')") as c:
                    stats["today_visitors"] = (await c.fetchone())[0] or 0
        except Exception:
            stats["today_visitors"] = 0
        return stats

    # ═══ إعدادات الموقع ═══

    async def set_site_setting(self, key: str, value: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS site_settings (
                        key TEXT PRIMARY KEY, value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.execute(
                    "INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                    (key, value, datetime.now().isoformat())
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False

    async def get_all_site_settings(self) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT key, value FROM site_settings") as cursor:
                    return {r[0]: r[1] for r in await cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error getting site settings: {e}")
            return {}

    async def set_landing_page_setting(self, key: str, value: str) -> bool:
        return await self.set_site_setting(f"landing:{key}", value)

    async def get_landing_page_settings(self) -> dict:
        all_s = await self.get_all_site_settings()
        return {k[8:]: v for k, v in all_s.items() if k.startswith("landing:")}

    # ═══ زوار الويب ═══

    async def record_web_visitor(self, visitor: dict) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS web_visitors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, country TEXT DEFAULT 'unknown',
                        country_code TEXT DEFAULT '??', user_agent TEXT, device_type TEXT DEFAULT 'desktop',
                        browser TEXT, os TEXT, page TEXT, visit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.execute(
                    "INSERT INTO web_visitors (ip, country, country_code, user_agent, device_type, browser, os, page) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (visitor.get('ip', 'unknown'), visitor.get('country', 'unknown'),
                     visitor.get('country_code', '??'), visitor.get('user_agent', '')[:200],
                     visitor.get('device_type', 'desktop'), visitor.get('browser', '')[:50],
                     visitor.get('os', '')[:50], visitor.get('page', '/')[:100])
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error recording visitor: {e}")
            return False

    async def get_web_visitor_stats(self) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                async with db.execute("SELECT COUNT(*) FROM web_visitors") as c:
                    stats["total_visits"] = (await c.fetchone())[0] or 0
                async with db.execute("SELECT COUNT(DISTINCT ip) FROM web_visitors") as c:
                    stats["unique_visitors"] = (await c.fetchone())[0] or 0
                async with db.execute("SELECT COUNT(DISTINCT ip) FROM web_visitors WHERE visit_time >= datetime('now','-24 hours')") as c:
                    stats["today_visitors"] = (await c.fetchone())[0] or 0
                return stats
        except Exception as e:
            logger.error(f"Error getting web stats: {e}")
            return {}

    async def get_recent_web_visitors(self, limit: int = 20) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT ip, country, country_code, device_type, browser, os, page, visit_time FROM web_visitors ORDER BY visit_time DESC LIMIT ?",
                    (limit,)
                ) as cursor:
                    return [{"ip": r[0], "country": r[1], "country_code": r[2], "device_type": r[3],
                             "browser": r[4], "os": r[5], "page": r[6], "visit_time": r[7]}
                            for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting visitors: {e}")
            return []

    # ═══ مصادقة المشرف ═══

    async def verify_admin_password(self, password: str) -> bool:
        import hashlib, os as _os
        admin_hash = _os.getenv("ADMIN_PASSWORD_HASH", "")
        if not admin_hash:
            return False
        return hashlib.sha256(password.encode()).hexdigest() == admin_hash

    async def create_admin_session(self, token: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS admin_sessions (
                        token TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP
                    )
                """)
                await db.execute(
                    "INSERT INTO admin_sessions (token, created_at, expires_at) VALUES (?, ?, ?)",
                    (token, datetime.now().isoformat(), (datetime.now() + timedelta(days=7)).isoformat())
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating admin session: {e}")
            return False

    async def validate_admin_session(self, token: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM admin_sessions WHERE datetime(expires_at) < datetime('now')")
                await db.commit()
                async with db.execute("SELECT token FROM admin_sessions WHERE token = ?", (token,)) as cursor:
                    return bool(await cursor.fetchone())
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False

    # ═══ سجلات التحميل والإحصائيات ═══

    async def get_download_logs(self, page: int = 1, platform: str = "", per_page: int = 20) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                sql = "SELECT id, user_id, platform, title, file_size, downloaded_at FROM downloads WHERE 1=1"
                params = []
                if platform:
                    sql += " AND platform = ?"
                    params.append(platform)
                async with db.execute("SELECT COUNT(*) FROM downloads" + (f" WHERE platform = ?" if platform else ""),
                                     (params[0],) if params else ()) as c:
                    total = (await c.fetchone())[0]
                sql += " ORDER BY downloaded_at DESC LIMIT ? OFFSET ?"
                params.extend([per_page, (page - 1) * per_page])
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
                return {
                    "logs": [{"id": r[0], "user_id": r[1], "platform": r[2], "title": r[3],
                              "file_size": r[4], "downloaded_at": r[5]} for r in rows],
                    "total": total, "page": page, "pages": max(1, (total + per_page - 1) // per_page)
                }
        except Exception as e:
            logger.error(f"Error getting download logs: {e}")
            return {"logs": [], "total": 0, "page": 1, "pages": 0}

    async def get_download_trends(self, days: int = 14) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT date(downloaded_at) as d, COUNT(*) as c FROM downloads WHERE downloaded_at >= datetime('now', ?) GROUP BY d ORDER BY d",
                    (f"-{days} days",)
                ) as cursor:
                    return [{"date": r[0], "count": r[1]} for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting trends: {e}")
            return []

    # ═══ مكافآت الويب ═══

    async def create_reward_link(self, user_id: int, token: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS reward_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, token TEXT UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, claimed BOOLEAN DEFAULT 0,
                        claimed_by INTEGER
                    )
                """)
                await db.execute("INSERT INTO reward_links (user_id, token) VALUES (?, ?)", (user_id, token))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating reward link: {e}")
            return False

    async def claim_reward(self, token: str) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT id, user_id, claimed FROM reward_links WHERE token = ?", (token,)) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    return {"success": False, "message": "رابط غير صالح"}
                if row[2]:
                    return {"success": False, "message": "تم استلام المكافأة مسبقاً"}
                await db.execute("UPDATE reward_links SET claimed = 1 WHERE token = ?", (token,))
                await db.commit()
                return {"success": True, "message": "تم استلام المكافأة", "user_id": row[1]}
        except Exception as e:
            logger.error(f"Error claiming reward: {e}")
            return {"success": False, "message": "حدث خطأ"}

    async def redeem_points(self, user_id: int) -> dict:
        points = await self.get_user_points(user_id)
        if points < 100:
            return {"success": False, "message": "تحتاج 100 نقطة على الأقل"}
        await self.add_user_points(user_id, -100)
        prefix = "ttk-"
        import secrets
        key = prefix + secrets.token_hex(4)
        await self.create_activation_key(key=key, owner_name=str(user_id), usage_limit=5, notes="مكافأة نقاط")
        return {"success": True, "message": "تم استبدال النقاط بمفتاح تحميل", "key": key}
