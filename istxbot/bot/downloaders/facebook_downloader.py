"""
Facebook Video Downloader — uses yt-dlp with cookie support.
"""

import os
import asyncio
from typing import Optional, Tuple, List

import yt_dlp

from bot.downloaders.base_downloader import BaseDownloader


class FacebookDownloader(BaseDownloader):
    PLATFORM = "Facebook"
    MAX_RETRIES = 3
    COOKIE_FILES = [
        'cookies_facebook.txt', 'cookies.txt',
        'data/cookies_facebook.txt', 'data/cookies.txt',
    ]

    def __init__(self):
        super().__init__()

    async def download(self, url: str) -> Tuple[bool, List[str], str]:
        return await self._download_with_retry(url, self._attempt_download)

    async def _attempt_download(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Single download attempt via yt-dlp."""
        cookies = self._find_cookies()
        ydl_opts = self._get_common_ydl_opts(str(self._download_dir), {
            'format': 'best[ext=mp4]/best',
            'extract_flat': False,
        })
        if cookies:
            ydl_opts['cookiefile'] = cookies

        loop = asyncio.get_event_loop()

        def _run():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        return None, None, "فشل استخراج معلومات الفيديو"
                    filename = ydl.prepare_filename(info)
                    if not os.path.exists(filename):
                        return filename, info.get('title'), "لم يتم العثور على الملف بعد التحميل"
                    return filename, info.get('title', 'Facebook Video'), None
            except Exception as e:
                return None, None, str(e)

        filename, title, error = await loop.run_in_executor(None, _run)
        if error:
            return filename, title, error
        if filename and os.path.exists(filename):
            return filename, self._sanitize_filename(title) if title else 'Facebook_Video', None
        return None, None, "فشل التحميل"

    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        if not error:
            return "فشل التحميل من Facebook. حاول مرة أخرى."
        self.logger.warning(f"Facebook download failed: {error[:100]}")
        error_lower = error.lower()
        error_map = {
            'deleted': "❌ المنشور محذوف أو غير موجود.",
            'private': "❌ المحتوى خاص وغير متاح للجمهور.",
            'not found': "❌ الرابط غير صحيح أو المحتوى غير موجود.",
            'timeout': "❌ انتهت مهلة التحميل. جرب مرة أخرى.",
            'network': "❌ مشكلة في الاتصال. تحقق من الإنترنت وحاول مرة أخرى.",
            'login': "❌ Facebook يتطلب تسجيل الدخول.",
            'restricted': "❌ المحتوى مقيد ولا يمكن تحميله.",
        }
        for key, msg in error_map.items():
            if key in error_lower:
                return msg
        return "❌ فشل التحميل من Facebook. حاول مرة أخرى."
