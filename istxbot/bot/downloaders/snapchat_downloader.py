import yt_dlp
import asyncio
import logging
import os
import re
import json
from pathlib import Path
from typing import Optional, Tuple, List
from urllib.parse import urlparse, parse_qs
from datetime import datetime

logger = logging.getLogger(__name__)

class SnapchatDownloader:
    def __init__(self):
        self.download_dir = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._max_retries = 3
        self._base_delay = 1.0
        self._user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
        
        self.cookies_paths = [
            'data/cookies_snapchat.txt',
            'cookies_snapchat.txt',
            'data/cookies.txt',
            'cookies.txt'
        ]

    def _normalize_url(self, url: str) -> str:
        """Normalize Snapchat URLs"""
        url = url.strip()
        
        if 't.snapchat.com' in url:
            return url
        
        if 'spotlight' in url:
            return url
        
        if 'snap.com/spotlight' in url:
            return url
        
        if '/add/' in url or '/discover/' in url:
            raise ValueError("User profiles and stories are not supported")
        
        if 'story.snapchat.com' in url:
            raise ValueError("Stories are not supported")
            
        return url

    def _resolve_short_url(self, url: str) -> str:
        """Resolve t.snapchat.com short URLs to get actual spotlight URL"""
        import requests
        
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
            final_url = response.url
            
            if 'spotlight' in final_url:
                return final_url
            
            if '/@' in final_url and '/spotlight/' in final_url:
                return final_url
                
            return url
            
        except Exception:
            return url

    def _get_cookies_path(self) -> Optional[str]:
        """Find available Snapchat cookies file"""
        for path in self.cookies_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        return None

    def _get_ydl_opts(self) -> dict:
        """Get yt-dlp options for Snapchat"""
        cookies_path = self._get_cookies_path()
        
        opts = {
            'format': 'best[ext=mp4]/bestvideo+bestaudio/best',
            'outtmpl': str(self.download_dir / 'snapchat_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'user_agent': self._user_agent,
            'http_headers': {
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://www.snapchat.com/',
                'Origin': 'https://www.snapchat.com',
            },
            'timeout': 60,
            'extract_flat': False,
            'cookiefile': cookies_path if cookies_path else None,
            'socket_timeout': 30,
        }
        
        if cookies_path:
            logger.info(f"Using cookies file: {cookies_path}")
        
        return opts

    def _get_fallback_opts(self) -> dict:
        """Get fallback options when primary method fails"""
        cookies_path = self._get_cookies_path()
        
        return {
            'format': 'best',
            'outtmpl': str(self.download_dir / 'snapchat_fallback_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.snapchat.com/',
            },
            'timeout': 90,
            'socket_timeout': 45,
            'cookiefile': cookies_path if cookies_path else None,
        }

    async def _download_with_ytdlp(self, url: str, opts: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Try download with yt-dlp"""
        loop = asyncio.get_event_loop()
        
        def _download():
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if not info:
                        return None, None, "فشل استخراج معلومات الفيديو"
                    
                    if info.get('live_status') == 'is_live':
                        return None, None, "❌ المحتوى المباشر غير مدعوم"
                    
                    if info.get('requested_subtitles'):
                        return None, None, "❌ هذا المحتوى غير متاح للتحميل"
                    
                    filename = ydl.prepare_filename(info)
                    title = info.get('title') or info.get('description') or 'Snapchat'
                    
                    if not os.path.exists(filename):
                        filename = next(
                            (f for f in os.listdir(self.download_dir) 
                             if f.startswith('snapchat_') or 'snapchat' in f.lower()),
                            None
                        )
                        if filename:
                            filename = str(self.download_dir / filename)
                    
                    if filename and os.path.exists(filename):
                        return filename, title, None
                    
                    return filename, title, "لم يتم العثور على الملف بعد التحميل"
                    
            except Exception as e:
                error_str = str(e)
                error_type = type(e).__name__
                
                if 'DownloadError' in error_type or 'HTTP Error' in error_str:
                    if '403' in error_str or 'Forbidden' in error_str:
                        return None, None, "❌ يحتاج هذا المحتوى لـ cookies"
                    if '404' in error_str or 'Not Found' in error_str:
                        return None, None, "❌ المحتوى غير موجود أو تم حذفه"
                    if 'Video unavailable' in error_str or 'unavailable' in error_str.lower():
                        return None, None, "❌ الفيديو غير متاح"
                    return None, None, error_str
                
                return None, None, str(e)
        
        return await loop.run_in_executor(None, _download)

    async def _download_with_retry(self, url: str) -> tuple[bool, list, str]:
        """Download with multiple attempts and fallback methods"""
        url = self._normalize_url(url)
        
        if 't.snapchat.com' in url:
            resolved_url = self._resolve_short_url(url)
            if resolved_url != url:
                logger.info(f"Resolved short URL: {url} -> {resolved_url}")
                url = resolved_url
        
        last_error = None
        
        for attempt in range(self._max_retries):
            try:
                logger.info(f"Snapchat download attempt {attempt + 1}/{self._max_retries}")
                
                opts = self._get_ydl_opts() if attempt == 0 else self._get_fallback_opts()
                filename, title, error = await self._download_with_ytdlp(url, opts)
                
                if filename and not error:
                    return True, [filename], title if title else 'Snapchat'
                
                last_error = error or "فشل التحميل"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} exception: {last_error}")
            
            if attempt < self._max_retries - 1:
                delay = self._base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        error_msg = self._get_user_friendly_error(last_error)
        return False, [], error_msg

    async def download(self, url: str) -> tuple[bool, list, str]:
        """Download Snapchat media"""
        try:
            return await self._download_with_retry(url)
        except ValueError as e:
            return False, [], str(e)
        except Exception as e:
            logger.error(f"Unexpected error in Snapchat download: {e}")
            return False, [], "❌ فشل التحميل من Snapchat"

    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        """Convert technical errors to user-friendly messages"""
        if not error:
            return "❌ فشل التحميل من Snapchat. حاول مرة أخرى."
        
        logger.warning(f"Snapchat download failed: {error[:150]}")
        
        error_lower = error.lower()
        
        if 'فشل استخراج معلومات الفيديو' in error or '404' in error_lower or 'not found' in error_lower:
            return "❌ الرابط غير صحيح أو المحتوى غير متاح. تأكد من الرابط وحاول مرة أخرى."
        
        error_messages = {
            'cookie': "❌ يحتاج Snapchat لـ cookies. أضف cookies في cookies_snapchat.txt أو data/cookies_snapchat.txt\n📖 استخدم إضافة 'Get cookies.txt LOCALLY' من متصفحك",
            '403': "❌ المحتوى مقيد أو يحتاج لـ cookies",
            '404': "❌ المحتوى غير موجود أو تم حذفه",
            'private': "❌ المحتوى خاص وغير متاح",
            'live': "❌ المحتوى المباشر غير مدعوم",
            'timeout': "❌ انتهت مهلة التحميل. جرب مرة أخرى.",
            'network': "❌ مشكلة في الاتصال. تحقق من الإنترنت.",
            'unavailable': "❌ المحتوى غير متاح للتحميل",
            'profile': "❌ تحميل الصفحات الشخصية غير مدعوم",
            'story': "❌ تحميل القصص (Stories) غير مدعوم حالياً",
            'spotlight': "❌ هذا المحتوى من Spotlight غير متاح",
            'not supported': "❌ نوع هذا المحتوى غير مدعوم",
            'تسجيل الدخول': "❌ يحتاج Snapchat لـ cookies",
        }
        
        for key, message in error_messages.items():
            if key in error_lower:
                return message
        
        if 'login' in error_lower or 'sign in' in error_lower:
            return "❌ يحتاج Snapchat لـ cookies. أضف cookies في cookies_snapchat.txt\n📖 استخدم إضافة 'Get cookies.txt LOCALLY' من متجر Chrome"
        
        return "❌ فشل التحميل من Snapchat. تأكد من الرابط وحاول مرة أخرى."

    async def check_url_valid(self, url: str) -> Tuple[bool, str]:
        """Check if Snapchat URL is valid and supported"""
        try:
            url = self._normalize_url(url)
            
            patterns = [
                r'snapchat\.com/spotlight/',
                r't\.snapchat\.com/',
                r'snap\.com/spotlight/',
            ]
            
            if not any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns):
                return False, "❌ نوع هذا الرابط غير مدعوم"
            
            if '/add/' in url or '/discover/' in url:
                return False, "❌ الصفحات الشخصية غير مدعومة"
            
            return True, ""
            
        except Exception as e:
            return False, f"❌ {str(e)}"

    async def get_media_info(self, url: str) -> Optional[dict]:
        """Get media information without downloading"""
        try:
            url = self._normalize_url(url)
            opts = self._get_ydl_opts()
            opts.update({
                'skip_download': True,
                'extract_flat': True,
            })
            
            loop = asyncio.get_event_loop()
            
            def _get_info():
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        return info
                except:
                    return None
            
            info = await loop.run_in_executor(None, _get_info)
            
            if info:
                return {
                    'title': info.get('title') or info.get('description') or 'Snapchat',
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'upload_date': info.get('upload_date'),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting media info: {e}")
            return None
