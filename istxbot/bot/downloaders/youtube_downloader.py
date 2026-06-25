"""
YouTube Video/Audio Downloader — uses yt-dlp.
"""

import os
import asyncio
from pathlib import Path
from typing import Optional, Tuple, List

import yt_dlp

from bot.downloaders.base_downloader import BaseDownloader
from bot.utils.helpers import sanitize_filename


class YtDlpDownloader(BaseDownloader):
    PLATFORM = "YouTube"
    MAX_RETRIES = 3
    COOKIE_FILES = [
        'cookies_youtube.txt', 'cookies.txt',
        'data/cookies_youtube.txt', 'data/cookies.txt',
    ]

    def __init__(self):
        super().__init__()

    def _get_ydl_opts(self, audio: bool = False, cookies_path: Optional[str] = None) -> dict:
        """Build yt-dlp options optimized for YouTube."""
        opts = {
            # Flexible format: prefer mp4, fall back to any format
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best',
            'outtmpl': str(self._download_dir / '%(title).80s_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,          # Try alternative formats on error
            'extractor_retries': 5,        # More retries for YouTube
            'retries': 5,
            'fragment_retries': 5,
            'socket_timeout': 60,
            'nocheckcertificate': True,
            'extract_flat': False,
            'merge_output_format': 'mp4',  # Ensure mp4 output when merging
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            },
        }

        if audio:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            opts['merge_output_format'] = 'mp3'

        if cookies_path and os.path.exists(cookies_path):
            opts['cookiefile'] = os.path.abspath(cookies_path)
            self.logger.info(f"Using cookies: {cookies_path}")

        return opts

    async def download(self, url: str) -> Tuple[bool, List[str], str]:
        return await self._download_with_retry(url, self._attempt_download)

    async def download_audio(self, url: str) -> Tuple[bool, List[str], str]:
        return await self._download_with_retry(url, self._attempt_download_audio)

    async def _attempt_download_audio(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        return await self._attempt_download_internal(url, audio=True)

    async def _attempt_download(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        return await self._attempt_download_internal(url, audio=False)

    async def _attempt_download_internal(
        self, url: str, audio: bool = False
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Single yt-dlp download attempt."""
        cookies = self._find_cookies()
        ydl_opts = self._get_ydl_opts(audio=audio, cookies_path=cookies)

        loop = asyncio.get_event_loop()

        def _run() -> Tuple[Optional[str], Optional[str], Optional[str]]:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        return None, None, "فشل استخراج معلومات الفيديو"

                    filename = ydl.prepare_filename(info)

                    # Handle audio post-processing filename
                    if audio:
                        filename = os.path.splitext(filename)[0] + '.mp3'

                    # yt-dlp may change extension during merge (webm→mp4)
                    if not os.path.exists(filename):
                        # Try common extensions
                        base = os.path.splitext(filename)[0]
                        for ext in ('.mp4', '.mkv', '.webm', '.m4a', '.mp3'):
                            alt = base + ext
                            if os.path.exists(alt):
                                filename = alt
                                break
                        else:
                            return filename, info.get('title'), "الملف غير موجود بعد التحميل"

                    return filename, info.get('title', 'YouTube Media'), None

            except Exception as e:
                return None, None, str(e)

        filename, title, error = await loop.run_in_executor(None, _run)

        if error:
            return filename, title, error

        if filename and os.path.exists(filename):
            safe = sanitize_filename(title) if title else 'YouTube_Media'
            return filename, safe, None

        return None, None, "فشل التحميل"

    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        if not error:
            return "❌ فشل التحميل من YouTube. حاول مرة أخرى."
        self.logger.warning(f"YouTube download failed: {error[:150]}")
        error_lower = error.lower()
        error_map = {
            'sign in': "🔒 YouTube يتطلب تسجيل الدخول. جاري تحديث الكوكيز...",
            'confirm you': "🤖 YouTube يطلب تأكيد بشري. جاري استخدام طريقة بديلة...",
            'video unavailable': "❌ الفيديو غير متاح أو محذوف.",
            'private video': "🔒 الفيديو خاص.",
            'region locked': "🌍 المحتوى مقفل في منطقتك.",
            'copyright': "⚠️ محتوى محمي بحقوق النشر.",
            'not found': "❌ الرابط غير صحيح.",
            'timeout': "⏱️ انتهت مهلة التحميل. جرب مرة أخرى.",
            'network': "🌐 مشكلة اتصال. تحقق من الإنترنت.",
            'cookies': "🍪 يتطلب كوكيز YouTube.\nاستخدم إضافة Get cookies.txt من المتصفح.",
            'unable to download': "❌ فشل التحميل. قد يكون الفيديو محذوفاً أو محمياً.",
            'age restricted': "🔞 فيديو مقيد بالعمر. أضف كوكيز YouTube للمتابعة.",
        }
        for key, msg in error_map.items():
            if key in error_lower:
                return msg
        return "❌ فشل التحميل من YouTube. تأكد من صحة الرابط."
