"""خلط عمليات الحفظ والتحميل — JSON persistence layer"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DAILY_LIMITS_FILE = DATA_DIR / "daily_limits.json"
MONTHLY_USERS_FILE = DATA_DIR / "monthly_users.json"
USER_TIERS_FILE = DATA_DIR / "user_tiers.json"
USER_POINTS_FILE = DATA_DIR / "user_points.json"
USER_NAMES_FILE = DATA_DIR / "user_names.json"
STATS_FILE = DATA_DIR / "stats.json"
POINTS_RESET_FILE = DATA_DIR / "points_reset.json"


class PersistenceMixin:
    """عمليات حفظ وتحميل البيانات إلى ملفات JSON"""

    def _save_user_attempts(self):
        try:
            data = {str(k): v for k, v in self.user_attempts.items()}
            with open(DATA_DIR / "user_attempts.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user attempts: {e}")

    def _load_user_attempts(self):
        try:
            attempts_file = DATA_DIR / "user_attempts.json"
            if not attempts_file.exists():
                return
            with open(attempts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.user_attempts = {int(k): v for k, v in data.items()}
            logger.info(f"Loaded user attempts: {len(self.user_attempts)}")
        except Exception as e:
            logger.error(f"Error loading user attempts: {e}")

    def _save_daily_limits(self):
        try:
            data = {}
            for user_id, (count, date) in self.user_daily_downloads.items():
                data[str(user_id)] = {'count': count, 'date': date.isoformat()}
            with open(DAILY_LIMITS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving daily limits: {e}")

    def _load_daily_limits(self):
        try:
            if not DAILY_LIMITS_FILE.exists():
                return
            with open(DAILY_LIMITS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            now = datetime.now()
            for user_id_str, user_data in data.items():
                user_id = int(user_id_str)
                count = user_data['count']
                date = datetime.fromisoformat(user_data['date'])
                if (now - date).days >= 1:
                    self.user_daily_downloads[user_id] = (0, now)
                else:
                    self.user_daily_downloads[user_id] = (count, date)
            logger.info(f"Loaded daily limits for {len(data)} users")
        except Exception as e:
            logger.error(f"Error loading daily limits: {e}")

    def _save_monthly_users(self):
        try:
            data = {str(uid): d.isoformat() for uid, d in self.monthly_users.items()}
            with open(MONTHLY_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving monthly users: {e}")

    def _load_monthly_users(self):
        try:
            if not MONTHLY_USERS_FILE.exists():
                return
            with open(MONTHLY_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            now = datetime.now()
            for user_id_str, date_str in data.items():
                user_id = int(user_id_str)
                date = datetime.fromisoformat(date_str)
                if (now - date).days <= 30:
                    self.monthly_users[user_id] = date
            self.stats.monthly_users = len(self.monthly_users)
        except Exception as e:
            logger.error(f"Error loading monthly users: {e}")

    def _save_user_tiers(self):
        try:
            data = {str(uid): t.name for uid, t in self.user_tiers.items()}
            with open(USER_TIERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user tiers: {e}")

    def _load_user_tiers(self):
        try:
            if not USER_TIERS_FILE.exists():
                return
            with open(USER_TIERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            from . import UserTier
            for user_id_str, tier_name in data.items():
                self.user_tiers[int(user_id_str)] = UserTier[tier_name]
        except Exception as e:
            logger.error(f"Error loading user tiers: {e}")

    def _save_user_points(self):
        try:
            with open(USER_POINTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_points, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user points: {e}")

    def _load_user_points(self):
        try:
            if not USER_POINTS_FILE.exists():
                return
            with open(USER_POINTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.user_points = {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading user points: {e}")

    def _save_user_names(self):
        try:
            data = {str(uid): n for uid, n in self.user_names.items()}
            with open(USER_NAMES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user names: {e}")

    def _load_user_names(self):
        try:
            if not USER_NAMES_FILE.exists():
                return
            with open(USER_NAMES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.user_names = {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading user names: {e}")

    def _save_points_reset_time(self):
        try:
            data = {}
            if self.points_reset_time:
                data['reset_time'] = self.points_reset_time.isoformat()
            with open(POINTS_RESET_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving points reset time: {e}")

    def _load_points_reset_time(self):
        try:
            if not POINTS_RESET_FILE.exists():
                return
            with open(POINTS_RESET_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'reset_time' in data:
                self.points_reset_time = datetime.fromisoformat(data['reset_time'])
        except Exception as e:
            logger.error(f"Error loading points reset time: {e}")

    def _save_stats(self):
        try:
            data = {
                'total_downloads': self.stats.total_downloads,
                'successful_downloads': self.stats.successful_downloads,
                'failed_downloads': self.stats.failed_downloads,
                'concurrent_downloads': self.stats.concurrent_downloads,
                'average_time': self.stats.average_time,
                'total_wait_time': self.stats.total_wait_time,
                'vip_downloads': self.stats.vip_downloads,
                'premium_downloads': self.stats.premium_downloads,
                'free_downloads': self.stats.free_downloads,
                'total_users': self.stats.total_users,
                'monthly_users': self.stats.monthly_users,
            }
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")

    def _load_stats(self):
        try:
            if not STATS_FILE.exists():
                return
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.stats.total_downloads = data.get('total_downloads', 0)
            self.stats.successful_downloads = data.get('successful_downloads', 0)
            self.stats.failed_downloads = data.get('failed_downloads', 0)
            self.stats.concurrent_downloads = data.get('concurrent_downloads', 0)
            self.stats.average_time = data.get('average_time', 0.0)
            self.stats.total_wait_time = data.get('total_wait_time', 0.0)
            self.stats.vip_downloads = data.get('vip_downloads', 0)
            self.stats.premium_downloads = data.get('premium_downloads', 0)
            self.stats.free_downloads = data.get('free_downloads', 0)
            self.stats.total_users = data.get('total_users', 0)
            self.stats.monthly_users = data.get('monthly_users', 0)
        except Exception as e:
            logger.error(f"Error loading stats: {e}")

    def save_all_data(self):
        self._save_daily_limits()
        self._save_monthly_users()
        self._save_user_tiers()
        self._save_user_points()
        self._save_user_names()
        self._save_user_attempts()
        self._save_stats()
        logger.info("Saved all data to files")

    def load_all_data(self):
        self._load_daily_limits()
        self._load_monthly_users()
        self._load_user_tiers()
        self._load_user_points()
        self._load_user_names()
        self._load_user_attempts()
        self._load_stats()
        logger.info("Loaded all data from files")
