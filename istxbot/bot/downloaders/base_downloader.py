"""
Base Downloader Class — shared functionality for all platform downloaders.

Reduces ~60% code duplication across the 8 downloader modules.
"""

import os
import re
import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from abc import ABC, abstractmethod
from collections import defaultdict


class BaseDownloader(ABC):
    """Abstract base class for all social media downloaders."""

    # Override in subclass
    PLATFORM: str = "Unknown"
    MAX_RETRIES: int = 3
    COOKIE_FILES: List[str] = []
    YTDLP_COOKIE_FILES: List[str] = []

    # Track API health for failover
    _api_health: Dict[str, int] = defaultdict(int)
    _api_banned_until: Dict[str, float] = {}

    def __init__(self):
        self.logger = logging.getLogger(f"downloader.{self.PLATFORM}")
        self._download_dir = self._get_download_dir()

    def _get_download_dir(self) -> Path:
        """Get platform-specific download directory."""
        base = Path(os.getenv("DOWNLOAD_DIR", "/tmp/bot_downloads"))
        platform_dir = base / self.PLATFORM.lower()
        platform_dir.mkdir(parents=True, exist_ok=True)
        return platform_dir

    # ── Abstract interface ────────────────────────────────────

    @abstractmethod
    async def download(self, url: str) -> Tuple[bool, List[str], str]:
        """Download media from URL. Returns (success, file_paths, error_message)."""
        ...

    @abstractmethod
    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        """Translate raw error into user-facing Arabic message."""
        ...

    # ── Shared retry logic ────────────────────────────────────

    async def _download_with_retry(
        self, url: str,
        download_func,
        max_retries: int = None,
        base_delay: float = 2.0,
    ) -> Tuple[bool, List[str], str]:
        """Retry wrapper with exponential backoff.

        Args:
            url: Media URL
            download_func: Async callable → Tuple[Optional[str], Optional[str], Optional[str]]
            max_retries: Override MAX_RETRIES
            base_delay: Starting delay in seconds
        """
        retries = max_retries if max_retries is not None else self.MAX_RETRIES
        last_error = ""
        all_files = []

        for attempt in range(retries):
            try:
                file_path, title, error = await download_func(url)
                if file_path and not error:
                    if isinstance(file_path, list):
                        all_files.extend(file_path)
                    else:
                        all_files.append(file_path)
                    if title and title not in all_files:
                        all_files.append(title)
                    self.logger.info(
                        f"[{self.PLATFORM}] ✓ Download success on attempt {attempt + 1}: "
                        f"{len(all_files)} file(s)"
                    )
                    return True, all_files, ""
                last_error = error or "unknown download error"
                self.logger.warning(
                    f"[{self.PLATFORM}] Attempt {attempt + 1}/{retries} failed: {last_error}"
                )
            except Exception as e:
                last_error = str(e)
                self.logger.error(
                    f"[{self.PLATFORM}] Exception on attempt {attempt + 1}: {e}"
                )

            if attempt < retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        return False, [], self._get_user_friendly_error(last_error)

    # ── Shared yt-dlp helpers ─────────────────────────────────

    def _find_cookies(self, cookie_files: List[str] = None) -> Optional[str]:
        """Find first available cookie file."""
        search = cookie_files or self.COOKIE_FILES or self.YTDLP_COOKIE_FILES
        if not search:
            return None
        cookie_paths = [
            Path(os.getenv("COOKIE_DIR", "/home/ngm/bot_download_telegram/data")),
            Path("/home/ngm/bot_download_telegram/data"),
            Path("/home/ngm/bot_dev/data"),
            Path.cwd() / "data",
        ]
        for name in search:
            for base in cookie_paths:
                p = base / name
                if p.exists():
                    return str(p)
        return None

    def _get_common_ydl_opts(
        self, output_dir: str, extra_opts: Dict = None
    ) -> Dict[str, Any]:
        """Base yt-dlp options shared across platforms."""
        opts = {
            'outtmpl': f'{output_dir}/%(title).100s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0.0.0 Safari/537.36'
                ),
            },
        }
        # Add cookies if available
        cookies = self._find_cookies()
        if cookies:
            opts['cookiefile'] = cookies

        if extra_opts:
            opts.update(extra_opts)
        return opts

    # ── File utilities ────────────────────────────────────────

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Clean filename for OS compatibility."""
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', '_', name)
        return name[:200]

    @staticmethod
    def _is_video(path: str) -> bool:
        """Check if file is a video by extension."""
        return os.path.splitext(path)[1].lower() in (
            '.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v'
        )

    @staticmethod
    def _is_audio(path: str) -> bool:
        """Check if file is audio by extension."""
        return os.path.splitext(path)[1].lower() in (
            '.mp3', '.m4a', '.ogg', '.wav', '.flac', '.aac', '.opus'
        )

    @staticmethod
    def _is_image(path: str) -> bool:
        """Check if file is an image by extension."""
        return os.path.splitext(path)[1].lower() in (
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'
        )

    # ── Common error messages ─────────────────────────────────

    _COMMON_ERRORS = {
        'login': '🔒 {platform} يتطلب تسجيل الدخول. جاري تحديث الكوكيز...',
        'private': '🔒 هذا المحتوى خاص. لا يمكن تحميله.',
        'not_found': '❌ لم يتم العثور على المحتوى. تأكد من صحة الرابط.',
        'network': '🌐 خطأ في الاتصال بالشبكة. حاول مرة أخرى.',
        'timeout': '⏱️ انتهت مهلة التحميل. جاري إعادة المحاولة...',
        'blocked': '🚫 تم حظر الطلب من قبل {platform}. جاري استخدام طريقة بديلة...',
        'copyright': '⚠️ هذا المحتوى محمي بحقوق النشر.',
        'age_restricted': '🔞 هذا المحتوى مقيد بالعمر. لا يمكن تحميله.',
        'invalid_url': '❌ رابط غير صالح لمنصة {platform}.',
        'server_error': '🖥️ خطأ في خادم {platform}. حاول مرة أخرى لاحقاً.',
        'unknown': '❌ فشل التحميل من {platform}. تأكد من صحة الرابط.',
    }

    def _format_error(self, key: str, **kwargs) -> str:
        """Format an error message with platform name."""
        platform = kwargs.pop('platform', self.PLATFORM)
        template = self._COMMON_ERRORS.get(key, self._COMMON_ERRORS['unknown'])
        return template.format(platform=platform, **kwargs)

    # ── API health tracking ───────────────────────────────────

    @classmethod
    def _is_api_healthy(cls, api_url: str, max_failures: int = 3) -> bool:
        """Check if an API endpoint is healthy."""
        if api_url in cls._api_banned_until:
            if time.time() < cls._api_banned_until[api_url]:
                return False
            del cls._api_banned_until[api_url]
            cls._api_health[api_url] = 0
        return cls._api_health.get(api_url, 0) < max_failures

    @classmethod
    def _mark_api_failure(cls, api_url: str, ban_seconds: float = 300.0):
        """Mark API endpoint as failed; ban after threshold."""
        cls._api_health[api_url] += 1
        if cls._api_health[api_url] >= 3:
            cls._api_banned_until[api_url] = time.time() + ban_seconds
            logging.getLogger("downloader").warning(
                f"API {api_url} banned for {ban_seconds}s after {cls._api_health[api_url]} failures"
            )

    @classmethod
    def _mark_api_success(cls, api_url: str):
        """Reset API failure counter on success."""
        cls._api_health[api_url] = 0
        cls._api_banned_until.pop(api_url, None)

    # ── Service availability checks ──────────────────────────

    @staticmethod
    def _is_tool_installed(tool_name: str) -> bool:
        """Check if a CLI tool (e.g., ffmpeg, spotdl) is available."""
        try:
            subprocess.run(
                [tool_name, '--version'],
                capture_output=True, timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
