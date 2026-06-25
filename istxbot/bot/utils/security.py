import re
import urllib.parse
from typing import Tuple, Optional, List
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    pass


class InvalidURLError(SecurityError):
    pass


class XSSDetectedError(SecurityError):
    pass


class CRLFInjectionError(SecurityError):
    pass


class SQLInjectionDetectedError(SecurityError):
    pass


DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'on\w+\s*=\s*["\']?.*?["\']?',
    r'javascript:',
    r'data:text/html',
    r'data:application/[^,]*,.*<.*',
    r'vbscript:',
    r'eval\s*\(',
    r'fromCharCode',
    r'unescape',
    r'alert\s*\(',
    r'document\.',
    r'window\.',
]


CRLF_PATTERNS = [
    r'\r\n',
    r'\n\r',
    r'%0d%0a',
    r'%0a%0d',
    r'&#13;&#10;',
    r'&#x0d;&#x0a;',
]


SQL_INJECTION_PATTERNS = [
    r"[';]?\s*(or|and|union|select|insert|update|delete|drop|create|alter|exec|execute)\s",
    r"('\s*--\s*$)",
    r"('\s*#.*$)",
    r"('\s*/\*.*\*/)",
    r"('\s*(or|and)\s+\d+\s*=\s*\d+)",
    r"(\bunion\b.*\bselect\b)",
]


@lru_cache(maxsize=1000)
def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate URL for security issues
    
    Args:
        url: URL to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    if not isinstance(url, str):
        return False, "URL must be a string"
    
    if len(url) > 2048:
        return False, "URL too long (max 2048 characters)"
    
    try:
        parsed = urllib.parse.urlparse(url)
        
        if not parsed.scheme or parsed.scheme not in ('http', 'https'):
            return False, "URL must use HTTP or HTTPS protocol"
        
        if not parsed.netloc:
            return False, "Invalid URL format"
        
        if re.search(r'[^\x00-\x7F]', url):
            try:
                urllib.parse.quote(url, safe=':/?#[]@!$&\'()*+,;=%')
            except Exception as e:
                return False, f"URL encoding error: {str(e)}"
        
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"
    
    if detect_xss(url):
        return False, "XSS attack detected in URL"
    
    if detect_crlf_injection(url):
        return False, "CRLF injection detected in URL"
    
    if detect_sql_injection(url):
        return False, "SQL injection detected in URL"
    
    return True, None


def detect_xss(text: str) -> bool:
    """Detect XSS patterns in text"""
    text_lower = text.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning(f"XSS detected: {pattern[:50]}...")
            return True
    return False


def detect_crlf_injection(text: str) -> bool:
    """Detect CRLF injection patterns"""
    text_lower = text.lower()
    for pattern in CRLF_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning("CRLF injection detected")
            return True
    return False


def detect_sql_injection(text: str) -> bool:
    """Detect SQL injection patterns"""
    text_lower = text.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning("SQL injection detected")
            return True
    return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and injection
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return "file"
    
    filename = filename.strip()
    
    dangerous_chars = ['../', '..\\', '..', '/', '\\', '\x00', '\n', '\r', '<', '>', ':', '"', '|', '?', '*']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '_', filename)
    
    filename = filename[:200]
    
    if not filename or filename == '_' * len(filename):
        return "file"
    
    return filename


def sanitize_user_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injections
    
    Args:
        text: User input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    if not isinstance(text, str):
        text = str(text)
    
    text = text.strip()[:max_length]
    
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    return text


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Validate file extension against allowed list
    
    Args:
        filename: Filename to validate
        allowed_extensions: Set of allowed extensions (e.g., {'.mp4', '.jpg'})
        
    Returns:
        True if extension is allowed
    """
    if not filename:
        return False
    
    import os
    _, ext = os.path.splitext(filename.lower())
    return ext in allowed_extensions


def validate_file_size(size_bytes: int, max_size_bytes: int) -> bool:
    """
    Validate file size
    
    Args:
        size_bytes: File size in bytes
        max_size_bytes: Maximum allowed size in bytes
        
    Returns:
        True if size is within limit
    """
    return size_bytes > 0 and size_bytes <= max_size_bytes


def validate_path_traversal(path: str) -> bool:
    """
    Detect path traversal attempts
    
    Args:
        path: File path to validate
        
    Returns:
        True if path traversal detected (unsafe)
    """
    traversal_patterns = [
        r'\.\./',
        r'\.\.\\',
        r'%2e%2e%2f',
        r'%252e%252e%252f',
        r'..\.',
        r'%c0%ae',
    ]
    
    path_lower = path.lower()
    for pattern in traversal_patterns:
        if re.search(pattern, path_lower, re.IGNORECASE):
            logger.warning(f"Path traversal detected: {pattern}")
            return True
    return False


def is_safe_url(url: str, allowed_domains: Optional[List[str]] = None) -> bool:
    """
    Check if URL is safe and optionally from allowed domains
    
    Args:
        url: URL to check
        allowed_domains: Optional list of allowed domains
        
    Returns:
        True if URL is safe
    """
    is_valid, error = validate_url(url)
    if not is_valid:
        return False
    
    if allowed_domains is not None:
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            
            if domain.startswith('www.'):
                domain = domain[4:]
            
            if domain not in [d.lower() for d in allowed_domains]:
                return False
        except Exception:
            return False
    
    return True


def mask_sensitive_data(data: str, visible_chars: int = 4, mask_char: str = '*') -> str:
    """
    Mask sensitive data for logging
    
    Args:
        data: Sensitive data (e.g., token, password)
        visible_chars: Number of characters to keep visible
        mask_char: Character to use for masking
        
    Returns:
        Masked string
    """
    if not data:
        return ""
    
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    return data[:visible_chars] + mask_char * (len(data) - visible_chars)
