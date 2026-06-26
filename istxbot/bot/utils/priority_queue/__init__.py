"""
Priority Queue Manager — إدارة طابور التحميل بالأولوية
تم التقسيم: النماذج + العمليات الأساسية هنا، الحفظ/التحميل في _persistence.py
"""
import asyncio
import logging
import uuid
import heapq
from typing import Dict, Optional, Callable, List, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path

from ._persistence import PersistenceMixin

logger = logging.getLogger(__name__)

# ═══ مسارات الملفات ═══
DATA_DIR = Path("data")
TIER_LIMITS_FILE = DATA_DIR / "tier_limits.json"

# ═══ النماذج والثوابت ═══

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
    'YouTube': TaskPriority.MEDIUM, 'Instagram': TaskPriority.MEDIUM,
    'Spotify': TaskPriority.MEDIUM, 'TikTok': TaskPriority.LOW,
    'Twitter': TaskPriority.LOW, 'Facebook': TaskPriority.LOW,
    'SoundCloud': TaskPriority.LOW, 'Snapchat': TaskPriority.LOW,
    'Google Drive': TaskPriority.HIGH,
}

TIER_LIMITS = {
    UserTier.VIP: {'max_concurrent': 10, 'max_daily': 1000, 'priority_bonus': -2},
    UserTier.PREMIUM: {'max_concurrent': 5, 'max_daily': 100, 'priority_bonus': -1},
    UserTier.STANDARD: {'max_concurrent': 3, 'max_daily': 20, 'priority_bonus': 0},
    UserTier.FREE: {'max_concurrent': 1, 'max_daily': 10, 'priority_bonus': 1},
}

ATTEMPT_VALUES = {'VIP': 5, 'PREMIUM': 3, 'STANDARD': 2, 'FREE': 1}

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

# ═══ PriorityQueueManager ═══

class PriorityQueueManager(PersistenceMixin):
    """مدير طابور التحميل — أولويات، حدود يومية، نقاط، وإحصائيات"""

    def __init__(self, max_concurrent: int = 3, max_queue: int = 100,
                 timeout: int = 300, enable_points: bool = True):
        self._queue: List[PriorityTask] = []
        self._active_tasks: Dict[str, PriorityTask] = {}
        self._completed_tasks: Dict[str, PriorityTask] = {}
        self._max_concurrent = max_concurrent
        self._max_queue = max_queue
        self._timeout = timeout
        self._enable_points = enable_points
        self._processing = False
        self._lock = asyncio.Lock()

        # تتبع المستخدمين
        self.user_daily_downloads: Dict[int, Tuple[int, datetime]] = {}
        self.monthly_users: Dict[int, datetime] = {}
        self.user_tiers: Dict[int, UserTier] = {}
        self.user_points: Dict[int, int] = {}
        self.user_attempts: Dict[int, int] = {}
        self.user_names: Dict[int, str] = {}
        self._online_users: set = set()
        self._progress_callbacks: Dict[int, Callable] = {}

        # الإحصائيات ونظام النقاط
        self.stats = DownloadStats()
        self.points_reset_time: Optional[datetime] = None
        self._points_multiplier = 1.0
        self._tier_limits = dict(TIER_LIMITS)

        # مهام التنظيف
        self._cleanup_task: Optional[asyncio.Task] = None
        self._auto_reset_task: Optional[asyncio.Task] = None

    # ═══ إدارة المستويات والنقاط ═══

    def set_user_tier(self, user_id: int, tier: UserTier):
        self.user_tiers[user_id] = tier

    def get_user_tier(self, user_id: int) -> UserTier:
        return self.user_tiers.get(user_id, UserTier.FREE)

    def add_user_points(self, user_id: int, points: int):
        if self._enable_points:
            current = self.user_points.get(user_id, 0)
            self.user_points[user_id] = current + int(points * self._points_multiplier)

    def get_user_points(self, user_id: int) -> int:
        return self.user_points.get(user_id, 0)

    def _load_tier_limits(self) -> Optional[dict]:
        import json
        try:
            if TIER_LIMITS_FILE.exists():
                with open(TIER_LIMITS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return {UserTier[k]: v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading tier limits: {e}")
        return None

    def get_tier_limit(self, user_tier: UserTier, limit_type: str = 'max_daily') -> int:
        limits = self._tier_limits.get(user_tier, TIER_LIMITS.get(user_tier, {}))
        return limits.get(limit_type, 10)

    def get_user_daily_limit(self, user_id: int) -> int:
        tier = self.get_user_tier(user_id)
        return self.get_tier_limit(tier, 'max_daily')

    # ═══ إدارة المحاولات ═══

    def add_user_attempt(self, user_id: int):
        current = self.user_attempts.get(user_id, 0)
        self.user_attempts[user_id] = current + 1

    def reset_user_attempts(self, user_id: int):
        self.user_attempts[user_id] = 0

    def get_user_attempts(self, user_id: int) -> int:
        return self.user_attempts.get(user_id, 0)

    def check_user_attempts(self, user_id: int) -> Tuple[bool, Optional[str], int]:
        tier = self.get_user_tier(user_id)
        max_attempts = ATTEMPT_VALUES.get(tier.name, 1)
        current_attempts = self.get_user_attempts(user_id)
        if current_attempts >= max_attempts:
            return False, f"تجاوزت الحد الأقصى للمحاولات ({max_attempts})", current_attempts
        return True, None, current_attempts

    def set_progress_callback(self, user_id: int, callback: Callable):
        self._progress_callbacks[user_id] = callback

    def remove_progress_callback(self, user_id: int):
        self._progress_callbacks.pop(user_id, None)

    # ═══ نظام الأولوية ═══

    def _calculate_priority(self, user_id: int, platform: str, message_id: int = 0) -> int:
        tier = self.get_user_tier(user_id)
        base = PLATFORM_PRIORITY.get(platform, TaskPriority.MEDIUM)
        bonus = TIER_LIMITS.get(tier, {}).get('priority_bonus', 0)
        return max(0, int(base) + bonus)

    def _check_daily_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        limit = self.get_user_daily_limit(user_id)
        today = datetime.now().date()
        count, date = self.user_daily_downloads.get(user_id, (0, today))
        if date.date() != today:
            self.user_daily_downloads[user_id] = (0, today)
            count = 0
        if count >= limit:
            return False, f"تجاوزت الحد اليومي للتحميل ({limit})"
        return True, None

    # ═══ عمليات الطابور ═══

    async def add_download(self, user_id: int, url: str, platform: str,
                           message_id: int = 0, priority: Optional[int] = None) -> Tuple[bool, str, Optional[str]]:
        async with self._lock:
            # التحقق من الحد اليومي
            can_dl, error_msg = self._check_daily_limit(user_id)
            if not can_dl:
                return False, error_msg, None

            # التحقق من سعة الطابور
            if len(self._queue) + len(self._active_tasks) >= self._max_queue:
                return False, "الطابور ممتلئ حالياً، حاول لاحقاً", None

            # إنشاء المهمة
            task_id = str(uuid.uuid4())[:8]
            calculated_priority = priority if priority is not None else \
                self._calculate_priority(user_id, platform, message_id)

            task = PriorityTask(
                priority=calculated_priority,
                created_at=datetime.now(),
                task_id=task_id,
                user_id=user_id,
                url=url,
                platform=platform,
                message_id=message_id,
                user_tier=self.get_user_tier(user_id),
            )

            heapq.heappush(self._queue, task)
            self.add_user_attempt(user_id)

            # تحديث عداد التحميل اليومي
            today = datetime.now().date()
            count, _ = self.user_daily_downloads.get(user_id, (0, today))
            self.user_daily_downloads[user_id] = (count + 1, today)

            position = len(self._queue)
            logger.info(f"Added task {task_id} for user {user_id} ({platform}), queue position: {position}")
            return True, f"تمت الإضافة للطابور (الموقع: {position})", task_id

    async def get_queue_status(self, user_id: int) -> Dict:
        async with self._lock:
            user_tasks = [t for t in self._queue if t.user_id == user_id]
            active_user_tasks = [t for t in self._active_tasks.values() if t.user_id == user_id]

            return {
                'queue_length': len(self._queue),
                'active_tasks': len(self._active_tasks),
                'user_position': next((i+1 for i, t in enumerate(self._queue) if t.user_id == user_id), 0),
                'user_tasks_in_queue': len(user_tasks),
                'user_active_tasks': len(active_user_tasks),
                'total_completed': len(self._completed_tasks),
                'daily_limit': self.get_user_daily_limit(user_id),
                'daily_used': self.user_daily_downloads.get(user_id, (0, datetime.now()))[0],
            }

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        for task in self._queue:
            if task.task_id == task_id:
                return {'status': 'queued', 'position': self._queue.index(task) + 1}
        if task_id in self._active_tasks:
            return {'status': 'processing'}
        if task_id in self._completed_tasks:
            task = self._completed_tasks[task_id]
            return {'status': 'completed', 'error': task.error}
        return None

    # ═══ إدارة المستخدمين ═══

    def register_online_user(self, user_id: int):
        self._online_users.add(user_id)
        self.stats.total_users = max(self.stats.total_users, len(self._online_users))

    def unregister_online_user(self, user_id: int):
        self._online_users.discard(user_id)

    def register_monthly_user(self, user_id: int):
        self.monthly_users[user_id] = datetime.now()
        self.stats.monthly_users = len(self.monthly_users)

    def register_user_name(self, user_id: int, username: Union[str, None] = None,
                           first_name: Union[str, None] = None):
        if first_name:
            self.user_names[user_id] = first_name
        elif username:
            self.user_names[user_id] = username

    def get_user_name(self, user_id: int) -> str:
        return self.user_names.get(user_id, str(user_id))

    # ═══ نظام النقاط ═══

    def reset_all_points_if_needed(self):
        now = datetime.now()
        if self.points_reset_time and (now - self.points_reset_time).days < 7:
            return False
        self.user_points.clear()
        self.points_reset_time = now
        logger.info("Points reset for all users")
        return True

    async def _auto_reset_points_loop(self):
        while True:
            await asyncio.sleep(3600)
            self.reset_all_points_if_needed()

    # ═══ تنظيف وإحصائيات ═══

    def cleanup_old_monthly_users(self):
        cutoff = datetime.now() - timedelta(days=30)
        old_count = len(self.monthly_users)
        self.monthly_users = {uid: date for uid, date in self.monthly_users.items() if date > cutoff}
        self.stats.monthly_users = len(self.monthly_users)
        logger.info(f"Cleaned up monthly users: {old_count - len(self.monthly_users)} removed")

    def get_users_by_period(self, days: int = 1) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        return sum(1 for date in self.monthly_users.values() if date > cutoff)

    def get_users_since(self, date: datetime) -> int:
        return sum(1 for d in self.monthly_users.values() if d > date)

    async def get_user_stats_by_period(self, days: int = 1) -> Dict:
        cutoff = datetime.now() - timedelta(days=days)
        users = [uid for uid, date in self.monthly_users.items() if date > cutoff]
        downloads = sum(1 for t in self._completed_tasks.values()
                       if t.completed_at and t.completed_at > cutoff)
        return {'users': len(users), 'downloads': downloads, 'days': days}

    async def get_user_stats_by_date_range(self, from_date: datetime,
                                           to_date: Optional[datetime] = None) -> Dict:
        to = to_date or datetime.now()
        users = [uid for uid, date in self.monthly_users.items() if from_date <= date <= to]
        downloads = sum(1 for t in self._completed_tasks.values()
                       if t.completed_at and from_date <= t.completed_at <= to)
        return {'users': len(users), 'downloads': downloads}

    # ═══ إلغاء المهام ═══

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            for i, task in enumerate(self._queue):
                if task.task_id == task_id:
                    self._queue.pop(i)
                    heapq.heapify(self._queue)
                    logger.info(f"Cancelled task {task_id}")
                    return True
            if task_id in self._active_tasks:
                logger.info(f"Cannot cancel active task {task_id}")
                return False
        return False

    async def cancel_user_tasks(self, user_id: int) -> int:
        async with self._lock:
            cancelled = 0
            self._queue = [t for t in self._queue if t.user_id != user_id]
            heapq.heapify(self._queue)
            cancelled = len([t for t in self._queue if t.user_id == user_id])
        return cancelled

    # ═══ المتصدرين ═══

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        user_downloads: Dict[int, int] = {}
        for task in self._completed_tasks.values():
            if task.status == 'completed' and not task.error:
                user_downloads[task.user_id] = user_downloads.get(task.user_id, 0) + 1
        sorted_users = sorted(user_downloads.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{'user_id': uid, 'downloads': count,
                 'name': self.get_user_name(uid),
                 'tier': self.get_user_tier(uid).name}
                for uid, count in sorted_users]

    # ═══ التشغيل والإيقاف ═══

    async def start(self):
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_downloads())
        if self._auto_reset_task is None and self._enable_points:
            self._auto_reset_task = asyncio.create_task(self._auto_reset_points_loop())
        logger.info("Priority queue manager started")

    async def stop(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
        if self._auto_reset_task:
            self._auto_reset_task.cancel()
            self._auto_reset_task = None
        self.save_all_data()
        logger.info("Priority queue manager stopped")

    async def _cleanup_expired_downloads(self):
        while True:
            await asyncio.sleep(300)
            try:
                now = datetime.now()
                expired = [tid for tid, t in self._active_tasks.items()
                          if t.started_at and (now - t.started_at).seconds > self._timeout]
                for tid in expired:
                    task = self._active_tasks.pop(tid, None)
                    if task:
                        task.status = 'failed'
                        task.error = 'Download timeout'
                        task.completed_at = now
                        self._completed_tasks[tid] = task
                        self.stats.failed_downloads += 1
                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired downloads")
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")

    # ═══ معالجة الطابور ═══

    async def process_queue(self, download_func: Callable):
        self._processing = True
        logger.info("Queue processor started")
        while self._processing:
            async with self._lock:
                if not self._queue or len(self._active_tasks) >= self._max_concurrent:
                    await asyncio.sleep(0.5)
                    continue
                task = heapq.heappop(self._queue)

            task.status = 'processing'
            task.started_at = datetime.now()
            self._active_tasks[task.task_id] = task
            self.stats.concurrent_downloads = max(self.stats.concurrent_downloads, len(self._active_tasks))
            asyncio.create_task(self._execute_download(task, download_func))

    async def _execute_download(self, task: PriorityTask, download_func: Callable):
        try:
            result = await asyncio.wait_for(download_func(task), timeout=self._timeout)
            task.status = 'completed'
            task.completed_at = datetime.now()
            self.stats.successful_downloads += 1
            if task.user_tier == UserTier.VIP:
                self.stats.vip_downloads += 1
            elif task.user_tier == UserTier.PREMIUM:
                self.stats.premium_downloads += 1
            else:
                self.stats.free_downloads += 1
            logger.info(f"Task {task.task_id} completed successfully")
        except asyncio.TimeoutError:
            task.status = 'failed'
            task.error = 'Download timeout'
            task.completed_at = datetime.now()
            self.stats.failed_downloads += 1
        except Exception as e:
            task.status = 'failed'
            task.error = str(e)[:200]
            task.completed_at = datetime.now()
            self.stats.failed_downloads += 1
            logger.error(f"Task {task.task_id} failed: {e}")
        finally:
            self._active_tasks.pop(task.task_id, None)
            self._completed_tasks[task.task_id] = task
            self.stats.total_downloads += 1
            if task.completed_at and task.started_at:
                elapsed = (task.completed_at - task.started_at).total_seconds()
                self.stats.average_time = ((self.stats.average_time * (self.stats.total_downloads - 1)) + elapsed) / self.stats.total_downloads
            callback = self._progress_callbacks.get(task.user_id)
            if callback:
                try:
                    callback(task)
                except Exception:
                    pass

# ═══ Singleton ═══

_queue_manager: Optional[PriorityQueueManager] = None

def get_queue_manager() -> Optional[PriorityQueueManager]:
    return _queue_manager

async def init_queue_manager(max_concurrent: int = 3, max_queue: int = 100,
                              timeout: int = 300, enable_points: bool = True) -> PriorityQueueManager:
    global _queue_manager
    _queue_manager = PriorityQueueManager(
        max_concurrent=max_concurrent, max_queue=max_queue,
        timeout=timeout, enable_points=enable_points
    )
    return _queue_manager
