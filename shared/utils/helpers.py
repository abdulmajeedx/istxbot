import os
import asyncio
import re
import time
from pathlib import Path
from typing import Optional, Dict
from functools import lru_cache

PLATFORM_PATTERNS = {
    'TikTok': [
        r'tiktok\.com/@',
        r'tiktok\.com/t/',
        r'tiktok\.com/[\w-]+/(?:video|photo)/\d+',
        r'vm\.tiktok\.com/',
        r'vt\.tiktok\.com/',
    ],
    'Snapchat': [
        r'snapchat\.com/spotlight/',
        r't\.snapchat\.com/',
        r'snap\.com/spotlight/',
        r'snapchat\.com/add/',
        r'snapchat\.com/@',
        r'story\.snapchat\.com/',
    ],
}

COMPILED_PATTERNS = {
    platform: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for platform, patterns in PLATFORM_PATTERNS.items()
}

_url_cache: Dict[str, tuple] = {}
_CACHE_SIZE = 1000
_CACHE_TTL = 3600

async def cleanup_downloads():
    try:
        download_dir = Path("downloads")
        if download_dir.exists():
            tasks = []
            for file in download_dir.iterdir():
                if file.is_file():
                    tasks.append(asyncio.to_thread(os.unlink, file))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        print(f"Error cleaning up: {e}")

def get_file_size_mb(filepath: str) -> float:
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except:
        return 0

def is_video_file(filename: str) -> bool:
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.webm'}
    return Path(filename).suffix.lower() in video_extensions

def is_audio_file(filename: str) -> bool:
    audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma', '.opus'}
    return Path(filename).suffix.lower() in audio_extensions

def is_image_file(filename: str) -> bool:
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    return Path(filename).suffix.lower() in image_extensions

def get_platform_from_url(url: str) -> Optional[str]:
    url_lower = url.lower().strip()
    
    if url_lower in _url_cache:
        cached_result, timestamp = _url_cache[url_lower]
        if time.time() - timestamp < _CACHE_TTL:
            return cached_result
    
    for platform, patterns in COMPILED_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(url_lower):
                _update_cache(url_lower, platform)
                return platform
    
    _update_cache(url_lower, None)
    return None

def _update_cache(url: str, result: Optional[str]):
    if len(_url_cache) >= _CACHE_SIZE:
        oldest_key = min(_url_cache.keys(), key=lambda k: _url_cache[k][1])
        del _url_cache[oldest_key]
    _url_cache[url] = (result, time.time())

def sanitize_filename(filename: str) -> str:
    from bot.utils.security import sanitize_filename as secure_sanitize_filename
    return secure_sanitize_filename(filename)

async def download_with_retry(url: str, download_func, max_retries: int = 3, base_delay: float = 1.0):
    for attempt in range(max_retries):
        try:
            return await download_func(url)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
    
    return None

def format_bytes(size_bytes):
    size_bytes = float(size_bytes)
    if size_bytes == 0:
        return "0B"
    size_name = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_name[i]}"
