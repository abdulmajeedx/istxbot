import asyncio
import logging
import uuid
import json
import os
from typing import Dict, Optional, Callable, List, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
import heapq
from pathlib import Path

logger = logging.getLogger(__name__)

# مسار ملف الحفظ
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DAILY_LIMITS_FILE = DATA_DIR / "daily_limits.json"
MONTHLY_USERS_FILE = DATA_DIR / "monthly_users.json"
USER_TIERS_FILE = DATA_DIR / "user_tiers.json"
USER_POINTS_FILE = DATA_DIR / "user_points.json"
USER_NAMES_FILE = DATA_DIR / "user_names.json"
STATS_FILE = DATA_DIR / "stats.json"
POINTS_RESET_FILE = DATA_DIR / "points_reset.json"
TIER_LIMITS_FILE = DATA_DIR / "tier_limits.json"

class TaskPriority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3

class UserTier(IntEnum):
    VIP = 0
    PREMIUM = 1
    STANDARD = 2
    FREE = 3

PLATFORM_PRIORITY = {
    'YouTube': TaskPriority.MEDIUM,
    'Instagram': TaskPriority.MEDIUM,
    'Spotify': TaskPriority.MEDIUM,
    'TikTok': TaskPriority.LOW,
    'Twitter': TaskPriority.LOW,
    'Facebook': TaskPriority.LOW,
    'SoundCloud': TaskPriority.LOW,
    'Snapchat': TaskPriority.LOW,
    'Google Drive': TaskPriority.HIGH,
}

TIER_LIMITS = {
    UserTier.VIP: {'max_concurrent': 10, 'max_daily': 1000, 'priority_bonus': -2},
    UserTier.PREMIUM: {'max_concurrent': 5, 'max_daily': 100, 'priority_bonus': -1},
    UserTier.STANDARD: {'max_concurrent': 3, 'max_daily': 20, 'priority_bonus': 0},
    UserTier.FREE: {'max_concurrent': 1, 'max_daily': 10, 'priority_bonus': 1},
}

# قيم المحاولات لكل محاولة
ATTEMPT_VALUES = {
    'VIP': 5,
    'PREMIUM': 3,
    'STANDARD': 2,
    'FREE': 1,
}

@dataclass(order=True)
class PriorityTask:
    priority: int = field(compare=True)
    created_at: datetime = field(compare=True)
    task_id: str = field(compare=False)
    user_id: int = field(compare=False)
    url: str = field(compare=False)
    platform: str = field(compare=False)
    message_id: int = field(compare=False)
    status: str = field(default='pending', compare=False)
    started_at: Optional[datetime] = field(default=None, compare=False)
    completed_at: Optional[datetime] = field(default=None, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    user_tier: UserTier = field(default=UserTier.FREE, compare=False)
    points_used: int = field(default=0, compare=False)

@dataclass
class DownloadStats:
    total_downloads: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    concurrent_downloads: int = 0
    average_time: float = 0.0
    total_wait_time: float = 0.0
    vip_downloads: int = 0
    premium_downloads: int = 0
    free_downloads: int = 0
    total_users: int = 0
    monthly_users: int = 0

class PriorityQueueManager:
    def __init__(
        self,
        max_concurrent_downloads: int = 3,
        max_queue_size: int = 100,
        timeout_seconds: int = 300,
        enable_points: bool = True
    ):
        self.max_concurrent = max_concurrent_downloads
        self.max_queue = max_queue_size
        self.timeout = timeout_seconds
        self.enable_points = enable_points
        
        self.queue: List[PriorityTask] = []
        self.active_downloads: Dict[str, PriorityTask] = {}
        self.user_tasks: Dict[int, List[str]] = {}
        
        self.stats = DownloadStats()
        
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self._progress_callbacks: Dict[int, Callable] = {}
        
        self.user_tiers: Dict[int, UserTier] = {}
        self.user_points: Dict[int, int] = {}
        self.user_daily_downloads: Dict[int, Tuple[int, datetime]] = {}
        self.user_attempts: Dict[int, int] = {}
        self.user_names: Dict[int, str] = {}
        self.online_users: set = set()
        self.monthly_users: Dict[int, datetime] = {}
        self.points_reset_time: Optional[datetime] = None

        self._cleanup_task = None
        self._reset_points_task = None
        self._running = False

        self.task_counter = 0

    def set_user_tier(self, user_id: int, tier: UserTier):
        self.user_tiers[user_id] = tier
        self._save_user_tiers()
        logger.info(f"Set user {user_id} tier to {tier.name}")

    def get_user_tier(self, user_id: int) -> UserTier:
        return self.user_tiers.get(user_id, UserTier.FREE)

    def add_user_points(self, user_id: int, points: int):
        if user_id not in self.user_points:
            self.user_points[user_id] = 0
        self.user_points[user_id] += points
        self._save_user_points()
        logger.info(f"Added {points} points to user {user_id}. Total: {self.user_points[user_id]}")

    def get_user_points(self, user_id: int) -> int:
        return self.user_points.get(user_id, 0)

    def _load_tier_limits(self) -> Optional[dict]:
        """قراءة حدود المستويات من الملف"""
        try:
            if TIER_LIMITS_FILE.exists():
                with open(TIER_LIMITS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tier limits: {e}")
        
        return None

    def get_tier_limit(self, user_tier: UserTier, limit_type: str = 'max_daily') -> int:
        """الحصول على حد معين للمستوى"""
        custom_limits = self._load_tier_limits()
        
        if custom_limits and user_tier.name in custom_limits:
            value = custom_limits[user_tier.name].get(limit_type)
            if value is not None:
                return value
        
        if limit_type in TIER_LIMITS[user_tier]:
            return TIER_LIMITS[user_tier][limit_type]
        
        return 10

    def get_user_daily_limit(self, user_id: int) -> int:
        """الحصول على الحد اليومي للمستخدم بناءً على النقاط"""
        user_tier = self.get_user_tier(user_id)
        tier_limit = self.get_tier_limit(user_tier, 'max_daily')
        user_points = self.get_user_points(user_id)

        if user_points > 0:
            return user_points
        return tier_limit

    def add_user_attempt(self, user_id: int):
        """زيادة محاولات المستخدم"""
        if user_id not in self.user_attempts:
            self.user_attempts[user_id] = 0
        self.user_attempts[user_id] += 1
        logger.info(f"Added attempt for user {user_id}. Total attempts: {self.user_attempts[user_id]}")
        self._save_user_attempts()
    
    def reset_user_attempts(self, user_id: int):
        """إعادة تعيين محاولات المستخدم"""
        self.user_attempts[user_id] = 0
        logger.info(f"Reset attempts for user {user_id}")
        self._save_user_attempts()
    
    def get_user_attempts(self, user_id: int) -> int:
        """الحصول على عدد محاولات المستخدم"""
        return self.user_attempts.get(user_id, 0)
    
    def check_user_attempts(self, user_id: int) -> Tuple[bool, Optional[str], int]:
        """
        التحقق من تجاوز محاولات المستخدم
        
        Returns:
            (allowed, message, current_attempts)
        """
        user_tier = self.get_user_tier(user_id)
        current_attempts = self.get_user_attempts(user_id)
        
        # الحد الأقصى للمحاولات اليومية
        max_attempts = 50 if user_tier == UserTier.VIP else (
            30 if user_tier == UserTier.PREMIUM else (
                20 if user_tier == UserTier.STANDARD else 10
            )
        )
        
        if current_attempts >= max_attempts:
            return False, f"❌ تجاوزت الحد اليومي للمحاولات ({max_attempts} محاولة). انتظر غداً.", current_attempts
        
        return True, None, current_attempts
    
    def _save_user_attempts(self):
        """حفظ محاولات المستخدمين في ملف"""
        try:
            data = {str(k): v for k, v in self.user_attempts.items()}
            with open(DATA_DIR / "user_attempts.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved user attempts: {len(data)}")
        except Exception as e:
            logger.error(f"Error saving user attempts: {e}")
    
    def _load_user_attempts(self):
        """تحميل محاولات المستخدمين من ملف"""
        try:
            attempts_file = DATA_DIR / "user_attempts.json"
            if not attempts_file.exists():
                logger.debug("User attempts file does not exist")
                return
            
            with open(attempts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.user_attempts = {int(k): v for k, v in data.items()}
            logger.info(f"Loaded user attempts: {len(self.user_attempts)}")
        except Exception as e:
            logger.error(f"Error loading user attempts: {e}")
    
    def set_progress_callback(self, user_id: int, callback: Callable):
        self._progress_callbacks[user_id] = callback
    
    def remove_progress_callback(self, user_id: int):
        self._progress_callbacks.pop(user_id, None)
    
    def _save_daily_limits(self):
        """حفظ حدود التحميل اليومي في ملف"""
        try:
            data = {}
            for user_id, (count, date) in self.user_daily_downloads.items():
                data[str(user_id)] = {
                    'count': count,
                    'date': date.isoformat()
                }
            
            with open(DAILY_LIMITS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved daily limits for {len(data)} users")
        except Exception as e:
            logger.error(f"Error saving daily limits: {e}")
    
    def _load_daily_limits(self):
        """تحميل حدود التحميل اليومي من ملف"""
        try:
            if not DAILY_LIMITS_FILE.exists():
                logger.debug("Daily limits file does not exist")
                return
            
            with open(DAILY_LIMITS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            now = datetime.now()
            loaded_users = 0
            
            for user_id_str, user_data in data.items():
                user_id = int(user_id_str)
                count = user_data['count']
                date = datetime.fromisoformat(user_data['date'])
                
                # التحقق من أن التاريخ ليس قديماً (أكثر من يوم)
                if (now - date).days >= 1:
                    # إعادة تعيين العداد إذا كان التاريخ قديماً
                    self.user_daily_downloads[user_id] = (0, now)
                    logger.debug(f"Reset daily limit for user {user_id} (old date)")
                else:
                    # الاحتفاظ بالعداد الحالي
                    self.user_daily_downloads[user_id] = (count, date)
                    loaded_users += 1
            
            logger.info(f"Loaded daily limits for {loaded_users} users")
        except Exception as e:
            logger.error(f"Error loading daily limits: {e}")
    
    def _save_monthly_users(self):
        """حفظ المستخدمين الشهريين في ملف"""
        try:
            data = {}
            for user_id, date in self.monthly_users.items():
                data[str(user_id)] = date.isoformat()
            
            with open(MONTHLY_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved monthly users: {len(data)}")
        except Exception as e:
            logger.error(f"Error saving monthly users: {e}")
    
    def _load_monthly_users(self):
        """تحميل المستخدمين الشهريين من ملف"""
        try:
            if not MONTHLY_USERS_FILE.exists():
                logger.debug("Monthly users file does not exist")
                return
            
            with open(MONTHLY_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            now = datetime.now()
            loaded_users = 0
            
            for user_id_str, date_str in data.items():
                user_id = int(user_id_str)
                date = datetime.fromisoformat(date_str)
                
                # التحقق من أن المستخدم زار خلال آخر 30 يوم
                if (now - date).days <= 30:
                    self.monthly_users[user_id] = date
                    loaded_users += 1
            
            self.stats.monthly_users = len(self.monthly_users)
            logger.info(f"Loaded monthly users: {loaded_users}")
        except Exception as e:
            logger.error(f"Error loading monthly users: {e}")
    
    def _save_user_tiers(self):
        """حفظ مستويات المستخدمين في ملف"""
        try:
            data = {}
            for user_id, tier in self.user_tiers.items():
                data[str(user_id)] = tier.name
            
            with open(USER_TIERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved user tiers: {len(data)}")
        except Exception as e:
            logger.error(f"Error saving user tiers: {e}")
    
    def _load_user_tiers(self):
        """تحميل مستويات المستخدمين من ملف"""
        try:
            if not USER_TIERS_FILE.exists():
                logger.debug("User tiers file does not exist")
                return
            
            with open(USER_TIERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            loaded_users = 0
            for user_id_str, tier_name in data.items():
                user_id = int(user_id_str)
                tier = UserTier[tier_name]
                self.user_tiers[user_id] = tier
                loaded_users += 1
            
            logger.info(f"Loaded user tiers: {loaded_users}")
        except Exception as e:
            logger.error(f"Error loading user tiers: {e}")
    
    
    def _save_user_points(self):
        """حفظ نقاط المستخدمين في ملف"""
        try:
            with open(USER_POINTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_points, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved user points: {len(self.user_points)}")
        except Exception as e:
            logger.error(f"Error saving user points: {e}")
    
    def _load_user_points(self):
        """تحميل نقاط المستخدمين من ملف"""
        try:
            if not USER_POINTS_FILE.exists():
                logger.debug("User points file does not exist")
                return

            with open(USER_POINTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.user_points = {int(k): v for k, v in data.items()}
            logger.info(f"Loaded user points: {len(self.user_points)}")
        except Exception as e:
            logger.error(f"Error loading user points: {e}")

    def _save_user_names(self):
        """حفظ أسماء المستخدمين في ملف"""
        try:
            data = {}
            for user_id, name in self.user_names.items():
                data[str(user_id)] = name

            with open(USER_NAMES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved user names: {len(data)}")
        except Exception as e:
            logger.error(f"Error saving user names: {e}")

    def _load_user_names(self):
        """تحميل أسماء المستخدمين من ملف"""
        try:
            if not USER_NAMES_FILE.exists():
                logger.debug("User names file does not exist")
                return

            with open(USER_NAMES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.user_names = {int(k): v for k, v in data.items()}
            logger.info(f"Loaded user names: {len(self.user_names)}")
        except Exception as e:
            logger.error(f"Error loading user names: {e}")

    def _save_points_reset_time(self):
        """حفظ وقت إعادة تعيين النقاط"""
        try:
            data = {}
            if self.points_reset_time:
                data['reset_time'] = self.points_reset_time.isoformat()

            with open(POINTS_RESET_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Saved points reset time: {self.points_reset_time}")
        except Exception as e:
            logger.error(f"Error saving points reset time: {e}")

    def _load_points_reset_time(self):
        """تحميل وقت إعادة تعيين النقاط"""
        try:
            if not POINTS_RESET_FILE.exists():
                logger.debug("Points reset file does not exist")
                return

            with open(POINTS_RESET_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'reset_time' in data:
                self.points_reset_time = datetime.fromisoformat(data['reset_time'])
                logger.info(f"Loaded points reset time: {self.points_reset_time}")
        except Exception as e:
            logger.error(f"Error loading points reset time: {e}")

    def _save_stats(self):
        """حفظ الإحصائيات في ملف"""
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
            
            logger.debug("Saved stats")
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def _load_stats(self):
        """تحميل الإحصائيات من ملف"""
        try:
            if not STATS_FILE.exists():
                logger.debug("Stats file does not exist")
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
            
            logger.info("Loaded stats")
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
    
    def save_all_data(self):
        """حفظ جميع البيانات"""
        self._save_daily_limits()
        self._save_monthly_users()
        self._save_user_tiers()
        self._save_user_points()
        self._save_user_names()
        self._save_user_attempts()
        self._save_stats()
        logger.info("Saved all data to files")

    def load_all_data(self):
        """تحميل جميع البيانات"""
        self._load_daily_limits()
        self._load_monthly_users()
        self._load_user_tiers()
        self._load_user_points()
        self._load_user_names()
        self._load_user_attempts()
        self._load_points_reset_time()
        self._load_stats()
        logger.info("Loaded all data from files")

    def _calculate_priority(
        self,
        user_id: int,
        platform: str,
        use_points: bool = False,
        points: int = 0
    ) -> int:
        user_tier = self.get_user_tier(user_id)
        base_priority = PLATFORM_PRIORITY.get(platform, TaskPriority.MEDIUM).value
        
        tier_bonus = TIER_LIMITS[user_tier]['priority_bonus']
        
        priority = base_priority + tier_bonus
        
        if use_points and self.enable_points:
            priority = max(0, priority - (points // 10))
            priority = min(priority, TaskPriority.CRITICAL.value)
        
        return priority

    def _check_daily_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        max_daily = self.get_user_daily_limit(user_id)

        if user_id not in self.user_daily_downloads:
            self.user_daily_downloads[user_id] = (0, datetime.now())
            return True, None

        count, date = self.user_daily_downloads[user_id]

        if (datetime.now() - date).days >= 1:
            self.user_daily_downloads[user_id] = (0, datetime.now())
            return True, None

        if count >= max_daily:
            return False, f"❌ تجاوزت الحد اليومي ({max_daily} تحميل). انتظر غداً أو ارتقِ للمستوى الأعلى."

        return True, None

    async def add_download(
        self,
        user_id: int,
        url: str,
        platform: str,
        message_id: int,
        priority: Optional[TaskPriority] = None,
        use_points: bool = False,
        points_to_use: int = 0
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        async with self._lock:
            daily_ok, daily_msg = self._check_daily_limit(user_id)
            if not daily_ok:
                return False, daily_msg, None
            
            if len(self.queue) >= self.max_queue:
                return False, "❌ قائمة الانتظار ممتلئة. انتظر قليلاً أو استخدم نقاط لتجاوز القائمة.", None
            
            if use_points and self.enable_points:
                available_points = self.get_user_points(user_id)
                if available_points < points_to_use:
                    return False, f"❌ نقاطك غير كافية. لديك {available_points} نقطة فقط.", None
                
                self.user_points[user_id] -= points_to_use
            
            final_priority = self._calculate_priority(
                user_id,
                platform,
                use_points,
                points_to_use
            )
            
            if priority is not None:
                final_priority = priority.value
            
            task = PriorityTask(
                priority=final_priority,
                created_at=datetime.now(),
                task_id=str(uuid.uuid4()),
                user_id=user_id,
                url=url,
                platform=platform,
                message_id=message_id,
                user_tier=self.get_user_tier(user_id),
                points_used=points_to_use
            )
            
            heapq.heappush(self.queue, task)
            
            if user_id not in self.user_tasks:
                self.user_tasks[user_id] = []
            self.user_tasks[user_id].append(task.task_id)
            
            self.stats.total_downloads += 1
            
            logger.info(
                f"Added download task {task.task_id} for user {user_id} from {platform}. "
                f"Priority: {final_priority}, Queue size: {len(self.queue)}"
            )
            
            return True, None, task.task_id

    async def get_queue_status(self, user_id: int) -> Dict:
        async with self._lock:
            user_tasks_in_queue = []
            user_position = None
            user_tier = self.get_user_tier(user_id)
            
            for i, task in enumerate(self.queue):
                if task.user_id == user_id and user_position is None:
                    user_position = i + 1
                if task.user_id == user_id:
                    user_tasks_in_queue.append(task.task_id)
            
            active_user_tasks = [
                task for task in self.active_downloads.values()
                if task.user_id == user_id
            ]
            
            return {
                'queue_size': len(self.queue),
                'active_downloads': len(self.active_downloads),
                'user_position': user_position,
                'user_tasks_in_queue': len(user_tasks_in_queue),
                'user_active_tasks': len(active_user_tasks),
                'user_tier': user_tier.name,
                'user_points': self.get_user_points(user_id),
                'user_daily_downloads': self.user_daily_downloads.get(user_id, (0, datetime.now()))[0],
                'user_daily_limit': self.get_user_daily_limit(user_id),
                'max_concurrent': self.get_tier_limit(user_tier, 'max_concurrent'),
                'total_downloads': self.stats.total_downloads,
                'successful_downloads': self.stats.successful_downloads,
                'failed_downloads': self.stats.failed_downloads,
                'average_time': f"{self.stats.average_time:.1f}s",
                'online_users': len(self.online_users),
                'monthly_users': self.stats.monthly_users,
            }

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        async with self._lock:
            for task in self.queue:
                if task.task_id == task_id:
                    return {
                        'task_id': task.task_id,
                        'status': task.status,
                        'platform': task.platform,
                        'created_at': task.created_at,
                        'position': self.queue.index(task) + 1
                    }
            
            if task_id in self.active_downloads:
                task = self.active_downloads[task_id]
                elapsed = (datetime.now() - task.started_at).total_seconds() if task.started_at else 0
                return {
                    'task_id': task.task_id,
                    'status': task.status,
                    'platform': task.platform,
                    'created_at': task.created_at,
                    'started_at': task.started_at,
                    'elapsed_time': f"{elapsed:.1f}s"
                }
            
            return None

    def register_online_user(self, user_id: int):
        """تسجيل مستخدم كمستخدم نشط حالياً"""
        self.online_users.add(user_id)
        self.stats.total_users = len(self.user_tiers)
        logger.debug(f"User {user_id} is now online. Total online: {len(self.online_users)}")
    
    def unregister_online_user(self, user_id: int):
        """إلغاء تسجيل المستخدم من النشطين"""
        self.online_users.discard(user_id)
        logger.debug(f"User {user_id} is now offline. Total online: {len(self.online_users)}")
    
    def register_monthly_user(self, user_id: int):
        """تسجيل مستخدم كزائر شهري"""
        now = datetime.now()

        if user_id in self.monthly_users:
            last_visit = self.monthly_users[user_id]
            if (now - last_visit).days >= 30:
                self.monthly_users[user_id] = now
                logger.debug(f"User {user_id} visited again after 30+ days")
        else:
            self.monthly_users[user_id] = now
            logger.debug(f"User {user_id} is a new monthly visitor")

        self.stats.monthly_users = len(self.monthly_users)
        self._save_monthly_users()

    def register_user_name(self, user_id: int, username: Union[str, None] = None, first_name: Union[str, None] = None):
        """تسجيل اسم المستخدم"""
        name = username or first_name or f"User{user_id}"
        if user_id not in self.user_names or self.user_names[user_id] != name:
            self.user_names[user_id] = name
            self._save_user_names()
            logger.debug(f"User {user_id} name registered: {name}")

    def get_user_name(self, user_id: int) -> str:
        """الحصول على اسم المستخدم"""
        return self.user_names.get(user_id, f"User{user_id}")

    def reset_all_points_if_needed(self):
        """إعادة تعيين النقاط عند الساعة 9 صباحاً بتوقيت مكة المكررة (GMT+3) - فقط النقاط المستهلكة"""
        now = datetime.now()

        if self.points_reset_time:
            last_reset = self.points_reset_time
            if (now - last_reset).days < 1:
                return

        now_makkah = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now.hour >= 9 and now.minute >= 0:
            if self.points_reset_time is None or (now - self.points_reset_time).days >= 1:
                logger.info(f"Checking points reset at {now} (9 AM Makkah time)")
                logger.info(f"Resetting daily downloads count, preserving user points")

                reset_count = 0
                for user_id in self.user_daily_downloads:
                    self.user_daily_downloads[user_id] = (0, now)
                    reset_count += 1

                self.points_reset_time = now
                self._save_daily_limits()
                self._save_points_reset_time()
                logger.info(f"Reset daily downloads for {reset_count} users at {now} (9 AM Makkah time)")

    async def _auto_reset_points_loop(self):
        """حلقة التحقق التلقائي لإعادة تعيين النقاط"""
        while self._running:
            try:
                self.reset_all_points_if_needed()
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in auto reset points loop: {e}")
                await asyncio.sleep(60)

    def cleanup_old_monthly_users(self):
        """تنظيف المستخدمين القدامى (أكثر من 30 يوم)"""
        now = datetime.now()
        users_to_remove = []
        
        for user_id, last_visit in self.monthly_users.items():
            if (now - last_visit).days > 30:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.monthly_users[user_id]
            logger.debug(f"Removed old monthly user {user_id}")
        
        if users_to_remove:
            self.stats.monthly_users = len(self.monthly_users)
            logger.info(f"Cleaned up {len(users_to_remove)} old monthly users")
    
    def get_users_by_period(self, days: int = 1) -> int:
        """
        الحصول على عدد المستخدمين خلال فترة زمنية محددة
        
        Args:
            days: عدد الأيام (الافتراضي: يوم واحد)
        
        Returns:
            int: عدد المستخدمين خلال الفترة المحددة
        """
        now = datetime.now()
        cutoff_date = now - timedelta(days=days)
        
        count = 0
        for user_id, last_visit in self.monthly_users.items():
            if last_visit >= cutoff_date:
                count += 1
        
        return count
    
    def get_users_since(self, date: datetime) -> int:
        """
        الحصول على عدد المستخدمين منذ تاريخ معين
        
        Args:
            date: التاريخ للبدء من عنده
        
        Returns:
            int: عدد المستخدمين منذ التاريخ المحدد
        """
        count = 0
        for user_id, last_visit in self.monthly_users.items():
            if last_visit >= date:
                count += 1
        
        return count
    
    async def get_user_stats_by_period(self, days: int = 1) -> Dict:
        """
        الحصول على إحصائيات المستخدمين خلال فترة زمنية محددة
        
        Args:
            days: عدد الأيام (الافتراضي: يوم واحد)
        
        Returns:
            Dict: إحصائيات المستخدمين خلال الفترة المحددة
        """
        now = datetime.now()
        cutoff_date = now - timedelta(days=days)
        
        users_in_period = []
        total_downloads = 0
        successful_downloads = 0
        
        for user_id, last_visit in self.monthly_users.items():
            if last_visit >= cutoff_date:
                users_in_period.append(user_id)
        
        return {
            'period_days': days,
            'users_count': len(users_in_period),
            'user_ids': users_in_period,
            'from_date': cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),
            'to_date': now.strftime('%Y-%m-%d %H:%M:%S'),
            'total_downloads': total_downloads,
            'successful_downloads': successful_downloads,
        }
    
    async def get_user_stats_by_date_range(self, from_date: datetime, to_date: Optional[datetime] = None) -> Dict:
        """
        الحصول على إحصائيات المستخدمين بين تاريخين
        
        Args:
            from_date: تاريخ البدء
            to_date: تاريخ النهاية (الافتراضي: الآن)
        
        Returns:
            Dict: إحصائيات المستخدمين في الفترة المحددة
        """
        if to_date is None:
            to_date = datetime.now()
        
        users_in_range = []
        
        for user_id, last_visit in self.monthly_users.items():
            if from_date <= last_visit <= to_date:
                users_in_range.append(user_id)
        
        return {
            'from_date': from_date.strftime('%Y-%m-%d %H:%M:%S'),
            'to_date': to_date.strftime('%Y-%m-%d %H:%M:%S'),
            'users_count': len(users_in_range),
            'user_ids': users_in_range,
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            for i, task in enumerate(self.queue):
                if task.task_id == task_id:
                    self.queue.pop(i)
                    heapq.heapify(self.queue)
                    logger.info(f"Cancelled task {task_id} from queue")
                    return True
            
            if task_id in self.active_downloads:
                logger.warning(f"Cannot cancel active task {task_id}")
                return False
            
            return False

    async def cancel_user_tasks(self, user_id: int) -> int:
        async with self._lock:
            cancelled = 0
            tasks_to_remove = []
            
            for i, task in enumerate(self.queue):
                if task.user_id == user_id:
                    tasks_to_remove.append(task.task_id)
            
            for task_id in tasks_to_remove:
                await self.cancel_task(task_id)
                cancelled += 1
            
            return cancelled

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        async with self._lock:
            user_stats = {}
            
            for task in self.queue:
                if task.user_id not in user_stats:
                    user_stats[task.user_id] = {
                        'user_id': task.user_id,
                        'tier': task.user_tier.name,
                        'total_downloads': 0,
                        'points_used': 0
                    }
                user_stats[task.user_id]['total_downloads'] += 1
                user_stats[task.user_id]['points_used'] += task.points_used
            
            for task in self.active_downloads.values():
                if task.user_id not in user_stats:
                    user_stats[task.user_id] = {
                        'user_id': task.user_id,
                        'tier': task.user_tier.name,
                        'total_downloads': 0,
                        'points_used': 0
                    }
                user_stats[task.user_id]['total_downloads'] += 1
                user_stats[task.user_id]['points_used'] += task.points_used
            
            sorted_users = sorted(
                user_stats.values(),
                key=lambda x: (x['total_downloads'], x['points_used']),
                reverse=True
            )
            
            return sorted_users[:limit]

    async def start(self):
        if not self._running:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_downloads())
            self._reset_points_task = asyncio.create_task(self._auto_reset_points_loop())
            logger.info("Priority Queue Manager started")

    async def stop(self):
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        if self._reset_points_task:
            self._reset_points_task.cancel()
            try:
                await self._reset_points_task
            except asyncio.CancelledError:
                pass
        logger.info("Priority Queue Manager stopped")

    async def _cleanup_expired_downloads(self):
        while self._running:
            try:
                await asyncio.sleep(60)
                
                now = datetime.now()
                async with self._lock:
                    expired_tasks = []
                    for task_id, task in list(self.active_downloads.items()):
                        if task.started_at and (now - task.started_at).total_seconds() > self.timeout:
                            expired_tasks.append(task_id)
                    
                    for task_id in expired_tasks:
                        task = self.active_downloads.pop(task_id, None)
                        if task:
                            task.status = 'timeout'
                            task.error = 'Timeout exceeded'
                            self.stats.failed_downloads += 1
                            logger.warning(f"Download timeout for task {task_id}")
                    
                    if expired_tasks:
                        logger.info(f"Cleaned up {len(expired_tasks)} expired downloads")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    async def process_queue(self, download_func: Callable):
        while True:
            try:
                async with self._lock:
                    if not self.queue:
                        await asyncio.sleep(1)
                        continue
                    
                    if len(self.active_downloads) >= self.max_concurrent:
                        await asyncio.sleep(1)
                        continue
                    
                    task = heapq.heappop(self.queue)
                    
                    user_tier = task.user_tier
                    max_concurrent_for_tier = self.get_tier_limit(user_tier, 'max_concurrent')
                    
                    concurrent_for_tier = sum(
                        1 for t in self.active_downloads.values()
                        if t.user_tier == user_tier
                    )
                    
                    if concurrent_for_tier >= max_concurrent_for_tier:
                        heapq.heappush(self.queue, task)
                        await asyncio.sleep(1)
                        continue
                    
                    self.active_downloads[task.task_id] = task
                    task.status = 'processing'
                    task.started_at = datetime.now()
                    self.stats.concurrent_downloads = len(self.active_downloads)
                
                asyncio.create_task(self._execute_download(task, download_func))
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                await asyncio.sleep(1)

    async def _execute_download(self, task: PriorityTask, download_func: Callable):
        async with self._semaphore:
            try:
                wait_time = (task.started_at - task.created_at).total_seconds() if task.started_at and task.created_at else 0.0
                
                logger.info(
                    f"Executing download task {task.task_id} for user {task.user_id}. "
                    f"Waited {wait_time:.1f}s. Platform: {task.platform}"
                )
                
                if task.user_id in self._progress_callbacks:
                    callback = self._progress_callbacks[task.user_id]
                else:
                    callback = None
                
                result = await download_func(task.url, callback)
                
                async with self._lock:
                    task.completed_at = datetime.now()
                    
                    if result[0]:
                        task.status = 'completed'
                        self.stats.successful_downloads += 1
                        
                        duration = (task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else 0.0
                        if self.stats.successful_downloads > 0:
                            total_duration = self.stats.average_time * (self.stats.successful_downloads - 1)
                            self.stats.average_time = (total_duration + duration) / self.stats.successful_downloads
                        
                        self.stats.total_wait_time += wait_time
                        
                        if task.user_tier == UserTier.VIP:
                            self.stats.vip_downloads += 1
                        elif task.user_tier == UserTier.PREMIUM:
                            self.stats.premium_downloads += 1
                        else:
                            self.stats.free_downloads += 1
                        
                        logger.info(
                            f"Download successful for task {task.task_id}. "
                            f"Duration: {duration:.1f}s, Wait time: {wait_time:.1f}s"
                        )
                    else:
                        task.status = 'failed'
                        task.error = result[2] if len(result) > 2 else 'Unknown error'
                        self.stats.failed_downloads += 1
                        logger.error(f"Download failed for task {task.task_id}: {task.error}")
                    
                    self.active_downloads.pop(task.task_id, None)
                    self.stats.concurrent_downloads = len(self.active_downloads)
                    
                    if task.user_id in self.user_tasks and task.task_id in self.user_tasks[task.user_id]:
                        self.user_tasks[task.user_id].remove(task.task_id)
                
                return result
                
            except Exception as e:
                async with self._lock:
                    task.status = 'error'
                    task.error = str(e)
                    self.stats.failed_downloads += 1
                    self.active_downloads.pop(task.task_id, None)
                    self.stats.concurrent_downloads = len(self.active_downloads)
                    
                    if task.user_id in self.user_tasks and task.task_id in self.user_tasks[task.user_id]:
                        self.user_tasks[task.user_id].remove(task.task_id)
                
                logger.error(f"Error executing download for task {task.task_id}: {e}")
                return False, "", str(e)

queue_manager = None

def get_queue_manager() -> Optional[PriorityQueueManager]:
    return queue_manager

def init_queue_manager(
    max_concurrent: int = 3,
    max_queue: int = 100,
    timeout: int = 300,
    enable_points: bool = True
) -> PriorityQueueManager:
    global queue_manager
    queue_manager = PriorityQueueManager(max_concurrent, max_queue, timeout, enable_points)
    return queue_manager