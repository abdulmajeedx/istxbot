import time
import asyncio
import logging
import os
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: int = 0):
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


@dataclass
class RateLimitConfig:
    max_requests: int
    time_window: int  # in seconds
    block_duration: int = 300  # in seconds


class RateLimiter:
    """Rate limiter using sliding window algorithm"""
    
    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        max_requests = int(os.getenv('RATE_LIMIT_MAX_PER_MIN', '30'))
        time_window = int(os.getenv('RATE_LIMIT_TIME_WINDOW', '60'))
        block_duration = int(os.getenv('RATE_LIMIT_BLOCK_DURATION', '300'))

        self.default_config = default_config or RateLimitConfig(
            max_requests=max_requests,
            time_window=time_window,
            block_duration=block_duration
        )
        
        self.user_requests: Dict[int, deque] = defaultdict(deque)
        self.user_blocks: Dict[int, datetime] = {}
        self.user_configs: Dict[int, RateLimitConfig] = {}
        self._lock = asyncio.Lock()
        
        self._cleanup_task = None
        self._running = False
    
    def set_user_config(self, user_id: int, config: RateLimitConfig):
        """Set custom rate limit for a user"""
        self.user_configs[user_id] = config
        logger.debug(f"Set rate limit config for user {user_id}")
    
    def get_user_config(self, user_id: int) -> RateLimitConfig:
        """Get rate limit config for a user"""
        return self.user_configs.get(user_id, self.default_config)
    
    def block_user(self, user_id: int, duration: Optional[int] = None):
        """Block a user for specified duration"""
        config = self.get_user_config(user_id)
        block_duration = duration or config.block_duration
        self.user_blocks[user_id] = datetime.now() + timedelta(seconds=block_duration)
        logger.warning(f"Blocked user {user_id} for {block_duration}s")
    
    def unblock_user(self, user_id: int):
        """Unblock a user"""
        self.user_blocks.pop(user_id, None)
        logger.info(f"Unblocked user {user_id}")
    
    def is_blocked(self, user_id: int) -> bool:
        """Check if user is currently blocked"""
        if user_id not in self.user_blocks:
            return False
        
        if datetime.now() > self.user_blocks[user_id]:
            self.unblock_user(user_id)
            return False
        
        return True
    
    def get_block_remaining_time(self, user_id: int) -> int:
        """Get remaining block time in seconds"""
        if user_id not in self.user_blocks:
            return 0
        
        remaining = int((self.user_blocks[user_id] - datetime.now()).total_seconds())
        return max(0, remaining)
    
    async def check_rate_limit(self, user_id: int, bypass_admin: bool = False) -> Tuple[bool, Optional[int]]:
        """
        Check if user is within rate limits
        
        Args:
            user_id: User ID to check
            bypass_admin: Allow admin to bypass rate limits
            
        Returns:
            (allowed, retry_after_seconds)
        """
        async with self._lock:
            if bypass_admin:
                return True, None
            
            if self.is_blocked(user_id):
                retry_after = self.get_block_remaining_time(user_id)
                logger.warning(f"User {user_id} is blocked, retry after {retry_after}s")
                return False, retry_after
            
            config = self.get_user_config(user_id)
            now = time.time()
            
            user_queue = self.user_requests[user_id]
            
            while user_queue and now - user_queue[0] > config.time_window:
                user_queue.popleft()
            
            if len(user_queue) >= config.max_requests:
                retry_after = int(config.time_window - (now - user_queue[0]))
                logger.warning(f"Rate limit exceeded for user {user_id}, retry after {retry_after}s")
                self.block_user(user_id)
                return False, retry_after
            
            user_queue.append(now)
            logger.debug(f"Request allowed for user {user_id}, count: {len(user_queue)}/{config.max_requests}")
            return True, None
    
    def reset_user(self, user_id: int):
        """Reset rate limit for a user"""
        self.user_requests.pop(user_id, None)
        self.user_blocks.pop(user_id, None)
        logger.info(f"Reset rate limit for user {user_id}")
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get rate limit statistics for a user"""
        config = self.get_user_config(user_id)
        user_queue = self.user_requests.get(user_id, deque())
        now = time.time()
        
        while user_queue and now - user_queue[0] > config.time_window:
            user_queue.popleft()
        
        return {
            'current_requests': len(user_queue),
            'max_requests': config.max_requests,
            'time_window': config.time_window,
            'is_blocked': self.is_blocked(user_id),
            'block_remaining': self.get_block_remaining_time(user_id)
        }
    
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Started rate limiter cleanup task")
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped rate limiter cleanup task")
    
    async def _cleanup_loop(self):
        """Periodic cleanup of old request records"""
        while self._running:
            try:
                await asyncio.sleep(60)
                async with self._lock:
                    now = time.time()
                    users_to_cleanup = []
                    
                    for user_id, user_queue in self.user_requests.items():
                        while user_queue and now - user_queue[0] > self.default_config.time_window * 10:
                            user_queue.popleft()
                        
                        if not user_queue and user_id not in self.user_blocks:
                            users_to_cleanup.append(user_id)
                    
                    for user_id in users_to_cleanup:
                        self.user_requests.pop(user_id, None)
                        self.user_blocks.pop(user_id, None)
                    
                    if users_to_cleanup:
                        logger.debug(f"Cleaned up {len(users_to_cleanup)} inactive users")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")


class RateLimitMiddleware:
    """Middleware for rate limiting in handlers"""
    
    def __init__(self, rate_limiter: RateLimiter, admin_id: int = 0):
        self.rate_limiter = rate_limiter
        self.admin_id = admin_id
    
    async def check(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check rate limit for user
        
        Returns:
            (allowed, error_message)
        """
        if os.getenv('RATE_LIMIT_ENABLED', '1').lower() not in ('1', 'true', 'yes'):
            return True, None

        bypass_admin = (user_id == self.admin_id) if self.admin_id else False
        allowed, retry_after = await self.rate_limiter.check_rate_limit(user_id, bypass_admin=bypass_admin)
        
        if not allowed:
            if retry_after:
                mins, secs = divmod(retry_after, 60)
                time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            else:
                time_str = "بضع ثوان"
            message = f"❌ تم حظرك مؤقتاً بسبب الإفراط في الطلبات. انتظر {time_str}"
            return False, message
        
        return True, None


_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter


async def check_rate_limit(user_id: int, bypass_admin: bool = False) -> Tuple[bool, Optional[int]]:
    """Check rate limit using global limiter"""
    return await get_rate_limiter().check_rate_limit(user_id, bypass_admin)
