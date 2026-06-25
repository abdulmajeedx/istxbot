import logging
import json
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    NETWORK = "network"
    DOWNLOAD = "download"
    VALIDATION = "validation"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    SYSTEM = "system"


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    user_id: int = 0
    platform: str = ""
    url: str = ""
    action: str = ""
    additional: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.additional is None:
            self.additional = {}
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        if data['additional']:
            data['additional'].update({
                'url': data['url'],
                'platform': data['platform']
            })
        return data


class BaseBotError(Exception):
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext()
        self.original_error = original_error
        self.timestamp = datetime.now()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'context': self.context.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'traceback': traceback.format_exc() if self.original_error else None
        }


class NetworkError(BaseBotError):
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.NETWORK, ErrorSeverity.HIGH, context, original_error)


class DownloadError(BaseBotError):
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.DOWNLOAD, ErrorSeverity.MEDIUM, context, original_error)


class ValidationError(BaseBotError):
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.VALIDATION, ErrorSeverity.LOW, context, original_error)


class DatabaseError(BaseBotError):
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.DATABASE, ErrorSeverity.HIGH, context, original_error)


class AuthenticationError(BaseBotError):
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH, context, original_error)


class AuthorizationError(BaseBotError):
    def __init__(self, message: str, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.AUTHORIZATION, ErrorSeverity.MEDIUM, context, original_error)


class RateLimitError(BaseBotError):
    def __init__(self, message: str, retry_after: int = 0, context: Optional[ErrorContext] = None, original_error: Optional[Exception] = None):
        self.retry_after = retry_after
        super().__init__(message, ErrorCategory.RATE_LIMIT, ErrorSeverity.LOW, context, original_error)


class DeadLetterQueue:
    """Queue for failed tasks that need to be retried or reviewed"""
    
    def __init__(self, max_size: int = 1000):
        self.queue: List[Dict[str, Any]] = []
        self.max_size = max_size
        self._lock = asyncio.Lock()
    
    async def add_error(self, error: BaseBotError, task_data: Optional[Dict] = None):
        """Add failed task to dead letter queue"""
        async with self._lock:
            if len(self.queue) >= self.max_size:
                self.queue.pop(0)
            
            error_entry = {
                'error': error.to_dict(),
                'task_data': task_data or {},
                'retry_count': 0,
                'added_at': datetime.now().isoformat()
            }
            
            self.queue.append(error_entry)
            logger.error(f"Added to dead letter queue: {error.__class__.__name__} - {error.message}")
    
    async def get_errors(
        self,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get errors from queue with optional filtering"""
        async with self._lock:
            filtered = self.queue.copy()
            
            if category:
                filtered = [e for e in filtered if e['error']['category'] == category.value]
            
            if severity:
                filtered = [e for e in filtered if e['error']['severity'] == severity.value]
            
            return filtered[-limit:]
    
    async def retry_task(self, index: int, retry_func) -> bool:
        """Retry a failed task"""
        async with self._lock:
            if index < 0 or index >= len(self.queue):
                return False
            
            task = self.queue[index]
            task['retry_count'] += 1
            
            try:
                await retry_func(task['task_data'])
                self.queue.pop(index)
                logger.info(f"Successfully retried task from dead letter queue (attempt {task['retry_count']})")
                return True
            except Exception as e:
                logger.error(f"Retry failed: {e}")
                if task['retry_count'] >= 3:
                    self.queue.pop(index)
                    logger.error("Removed task after max retries")
                return False
    
    async def clear_error(self, index: int) -> bool:
        """Remove error from queue"""
        async with self._lock:
            if index < 0 or index >= len(self.queue):
                return False
            
            self.queue.pop(index)
            return True
    
    async def clear_all(self):
        """Clear all errors from queue"""
        async with self._lock:
            self.queue.clear()
            logger.info("Cleared dead letter queue")
    
    async def get_stats(self) -> Dict:
        """Get statistics about the dead letter queue"""
        async with self._lock:
            by_category: Dict[str, int] = {}
            by_severity: Dict[str, int] = {}
            
            for entry in self.queue:
                category = entry['error']['category']
                severity = entry['error']['severity']
                
                by_category[category] = by_category.get(category, 0) + 1
                by_severity[severity] = by_severity.get(severity, 0) + 1
            
            return {
                'total_errors': len(self.queue),
                'by_category': by_category,
                'by_severity': by_severity
            }


class StructuredLogger:
    """Structured logging with JSON format and error tracking"""
    
    def __init__(self, name: str, dead_letter_queue: Optional[DeadLetterQueue] = None):
        self.logger = logging.getLogger(name)
        self.dead_letter_queue = dead_letter_queue
    
    def log_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        task_data: Optional[Dict] = None,
        include_traceback: bool = True
    ):
        """Log error with structured format"""
        if isinstance(error, BaseBotError):
            error_data = error.to_dict()
        else:
            error_data = {
                'error_type': error.__class__.__name__,
                'message': str(error),
                'category': ErrorCategory.SYSTEM.value,
                'severity': ErrorSeverity.MEDIUM.value,
                'context': context.to_dict() if context else {},
                'timestamp': datetime.now().isoformat(),
                'traceback': traceback.format_exc() if include_traceback else None
            }
        
        if context:
            error_data['context'].update(context.to_dict())
        
        self.logger.error(json.dumps(error_data, ensure_ascii=False, indent=2))
        
        if self.dead_letter_queue and isinstance(error, BaseBotError):
            asyncio.create_task(self.dead_letter_queue.add_error(error, task_data))
    
    def log_info(self, message: str, context: Optional[Dict] = None):
        """Log info message with structured format"""
        log_data: Dict[str, Any] = {
            'level': 'info',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        if context:
            log_data['context'] = context
        
        self.logger.info(json.dumps(log_data, ensure_ascii=False, indent=2))
    
    def log_warning(self, message: str, context: Optional[Dict] = None):
        """Log warning message with structured format"""
        log_data: Dict[str, Any] = {
            'level': 'warning',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        if context:
            log_data['context'] = context
        
        self.logger.warning(json.dumps(log_data, ensure_ascii=False, indent=2))
    
    def log_debug(self, message: str, context: Optional[Dict] = None):
        """Log debug message with structured format"""
        log_data: Dict[str, Any] = {
            'level': 'debug',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        if context:
            log_data['context'] = context
        
        self.logger.debug(json.dumps(log_data, ensure_ascii=False, indent=2))


def error_handler(func):
    """Decorator for automatic error handling and logging"""
    async def wrapper(*args, **kwargs):
        structured_logger = StructuredLogger(func.__name__)
        
        try:
            return await func(*args, **kwargs)
        except BaseBotError as e:
            structured_logger.log_error(e, e.context)
            raise
        except Exception as e:
            error = BaseBotError(str(e), context=ErrorContext())
            structured_logger.log_error(error, include_traceback=True)
            raise
    return wrapper


def safe_execute(func, default=None, context: Optional[ErrorContext] = None):
    """Execute function safely with error handling"""
    try:
        return func()
    except BaseBotError as e:
        logger = StructuredLogger(func.__name__)
        logger.log_error(e, context)
        return default
    except Exception as e:
        logger = StructuredLogger(func.__name__)
        error = BaseBotError(str(e), context=context)
        logger.log_error(error, include_traceback=True)
        return default


_global_dead_letter_queue: Optional[DeadLetterQueue] = None


def get_dead_letter_queue() -> DeadLetterQueue:
    """Get global dead letter queue instance"""
    global _global_dead_letter_queue
    if _global_dead_letter_queue is None:
        _global_dead_letter_queue = DeadLetterQueue()
    return _global_dead_letter_queue
