import yt_dlp
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from urllib.parse import urlparse, parse_qs
import requests

logger = logging.getLogger(__name__)

class TikTokDownloader:
    def __init__(self):
        self.download_dir = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._max_retries = 3
        self._base_delay = 1.0
        
        self.cookies_paths = [
            'data/cookies_tiktok.txt',
            'cookies_tiktok.txt',
            'data/cookies.txt',
            'cookies.txt'
        ]
        
        self.tiktok_domains = [
            'tiktok.com',
            'vm.tiktok.com',
            'vt.tiktok.com',
            'tiktokcdn.com',
        ]

    def _normalize_url(self, url: str) -> str:
        """Normalize TikTok URLs"""
        url = url.strip()

        parsed = urlparse(url)

        if parsed.netloc in ['vm.tiktok.com', 'vt.tiktok.com']:
            # Resolve short links to the final TikTok URL for better yt-dlp handling
            url = self._resolve_short_url(url)
            parsed = urlparse(url)
            if parsed.netloc in ['vm.tiktok.com', 'vt.tiktok.com']:
                return url

        # Clean query parameters and add working parameters
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if '?' not in clean_url:
            clean_url += '?is_from_webapp=1&sender_device=pc'
        
        return clean_url

    def _resolve_short_url(self, url: str) -> str:
        """Follow redirects for vm/vt short links"""
        try:
            resp = requests.head(url, allow_redirects=True, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            })
            final_url = resp.url
            if final_url and 'tiktok.com' in urlparse(final_url).netloc:
                return final_url
        except Exception as e:
            logger.warning(f"Failed to resolve TikTok short URL: {e}")
        return url

    def _get_cookies_path(self) -> Optional[str]:
        """Find available TikTok cookies file"""
        for path in self.cookies_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        return None

    def _download_via_tikwm(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Fallback download using tikwm.com public API"""
        try:
            api_url = "https://www.tikwm.com/api/"
            resp = requests.post(api_url, data={'url': url}, timeout=20, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Origin': 'https://www.tikwm.com',
                'Referer': 'https://www.tikwm.com/',
            })
            data = resp.json()
            if data.get('code') != 0:
                return None, None, "❌ فشل التحميل من TikTok (TikWM API)"
            
            play_url = data.get('data', {}).get('play')
            title = data.get('data', {}).get('title') or 'TikTok'
            
            if not play_url:
                return None, None, "❌ لم يتم العثور على الفيديو"
            
            filename = self.download_dir / f"tiktok_api_{hash(url)}.mp4"
            media = requests.get(play_url, timeout=30, stream=True, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            })
            media.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in media.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return str(filename), title, None
        except Exception as e:
            logger.error(f"TikWM fallback error: {e}")
            return None, None, "❌ فشل التحميل من TikTok (TikWM)"

    def _get_ydl_opts(self) -> dict:
        """Get yt-dlp options for TikTok"""
        cookies_path = self._get_cookies_path()
        
        opts = {
            'format': 'best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/bestvideo[vcodec^=avc1]+bestaudio/bestvideo+bestaudio/best',
            'format_sort': ['vcodec:h264', 'res', 'br'],
            'outtmpl': str(self.download_dir / 'tiktok_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://www.tiktok.com/',
                'Origin': 'https://www.tiktok.com',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Upgrade-Insecure-Requests': '1',
            },
            'timeout': 60,
            'socket_timeout': 30,
            'cookiefile': cookies_path if cookies_path else None,
            'extract_flat': False,
            'extractor_args': {
                'tiktok': {
                    'api_url': 'https://api22-normal-c-useast1a.tiktokv.com/aweme/v1/feed/',
                    'api_hostname': 'api22-normal-c-useast1a.tiktokv.com',
                }
            }
        }
        
        if cookies_path:
            logger.info(f"Using cookies file: {cookies_path}")
        
        return opts

    def _get_fallback_opts(self) -> dict:
        """Get fallback options when primary method fails"""
        cookies_path = self._get_cookies_path()
        
        return {
            'format': 'best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best',
            'outtmpl': str(self.download_dir / 'tiktok_fallback_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'http_headers': {
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.tiktok.com/',
            },
            'timeout': 90,
            'socket_timeout': 45,
            'cookiefile': cookies_path if cookies_path else None,
        }

    def _get_no_watermark_opts(self) -> dict:
        """Get options for no-watermark download"""
        cookies_path = self._get_cookies_path()
        
        return {
            'format': 'best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best',
            'format_sort': ['vcodec:h264', 'res', 'br'],
            'outtmpl': str(self.download_dir / 'tiktok_nowm_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.tiktok.com/',
                'Origin': 'https://www.tiktok.com',
            },
            'timeout': 60,
            'cookiefile': cookies_path if cookies_path else None,
            'extractor_args': {
                'tiktok': {
                    'format': 'download_addr',
                }
            }
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
                    
                    if info.get('requested_formats'):
                        info = info['requested_formats'][0]
                    
                    filename = ydl.prepare_filename(info)
                    title = info.get('title') or info.get('description') or info.get('uploader', 'TikTok')
                    
                    if not os.path.exists(filename):
                        downloaded_files = list(self.download_dir.glob('tiktok_*'))
                        if downloaded_files:
                            filename = str(downloaded_files[-1])
                        else:
                            filename = None
                    
                    if filename and os.path.exists(filename):
                        return filename, title, None
                    
                    return filename, title, "لم يتم العثور على الملف بعد التحميل"
                    
            except Exception as e:
                error_str = str(e)
                
                # yt-dlp sometimes fails with a generic extractor error for TikTok pages
                # Detect that specific message so we can fall back to the TikWM API immediately
                if 'Unable to extract webpage video data' in error_str:
                    return None, None, "yt_dlp_extractor_error: Unable to extract webpage video data"
                
                if 'HTTP Error 403' in error_str or '403' in error_str:
                    return None, None, "❌ يحتاج هذا المحتوى لـ cookies أو محظور في منطقتك"
                if 'HTTP Error 404' in error_str or '404' in error_str:
                    return None, None, "❌ المحتوى غير موجود أو تم حذفه"
                if 'Video unavailable' in error_str or 'unavailable' in error_str.lower():
                    return None, None, "❌ الفيديو غير متاح"
                if 'private' in error_str.lower():
                    return None, None, "❌ هذا المحتوى خاص وغير متاح للجمهور"
                if 'forbidden' in error_str.lower() or 'banned' in error_str.lower():
                    return None, None, "❌ المحتوى محظور في منطقتك"
                if 'sign in' in error_str.lower() or 'login' in error_str.lower():
                    return None, None, "❌ يحتاج TikTok لـ cookies"
                
                return None, None, error_str
        
        return await loop.run_in_executor(None, _download)

    async def _download_with_retry(self, url: str) -> tuple[bool, list, str]:
        """Download with multiple attempts and fallback methods (parallel primary, then fallbacks)"""
        url = self._normalize_url(url)
        last_error = None
        
        # Phase 1: Try all yt-dlp methods in parallel for speed
        ydl_opts_list = [self._get_ydl_opts(), self._get_no_watermark_opts(), self._get_fallback_opts()]
        tasks = [self._download_with_ytdlp(url, opts) for opts in ydl_opts_list]
        
        for i, coro in enumerate(tasks):
            try:
                logger.info(f"TikTok yt-dlp attempt {i + 1}/{len(ydl_opts_list)}")
                filename, title, error = await coro
                if filename and not error:
                    return True, [filename], title if title else 'TikTok'
                last_error = error or "فشل التحميل"
                logger.warning(f"Attempt {i + 1} failed: {last_error}")
                if last_error and 'yt_dlp_extractor_error' in str(last_error):
                    break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {i + 1} exception: {last_error}")
            if i < len(ydl_opts_list) - 1:
                await asyncio.sleep(self._base_delay)
        
        # Phase 2: TikWM public API fallback
        try:
            logger.info("TikTok: trying TikWM API fallback")
            filename, title, error = await asyncio.to_thread(self._download_via_tikwm, url)
            if filename and not error:
                return True, [filename], title or 'TikTok'
            last_error = error
        except Exception as e:
            last_error = str(e)
        
        # Phase 3: Secondary API fallback (ssstik.io style)
        try:
            logger.info("TikTok: trying secondary API fallback")
            filename, title, error = await asyncio.to_thread(self._download_via_secondary_api, url)
            if filename and not error:
                return True, [filename], title or 'TikTok'
            last_error = error
        except Exception as e:
            last_error = str(e)
        
        error_msg = self._get_user_friendly_error(last_error)
        return False, [], error_msg

    def _download_via_secondary_api(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Secondary fallback: use multiple public APIs"""
        import requests
        
        # Try ssstik.io-style API
        apis = [
            {
                'name': 'tikcdn',
                'url': 'https://tikcdn.io/api/v2/download',
                'method': 'POST',
                'data': {'url': url},
                'headers': {'User-Agent': self._user_agent, 'Origin': 'https://tikcdn.io'},
                'extractor': lambda r: (r.get('data', {}).get('video', {}).get('play_addr', {}).get('url_list', [''])[0],
                                        r.get('data', {}).get('desc'))
            },
        ]
        
        for api in apis:
            try:
                if api['method'] == 'POST':
                    resp = requests.post(api['url'], json=api['data'] if 'json' in str(api.get('data')) else api['data'], 
                                         headers=api['headers'], timeout=15)
                else:
                    resp = requests.get(api['url'], params=api.get('params', {}), headers=api['headers'], timeout=15)
                
                if resp.status_code != 200:
                    continue
                data = resp.json()
                play_url, desc = api['extractor'](data)
                if not play_url:
                    continue
                
                filename = self.download_dir / f"tiktok_api2_{hash(url)}.mp4"
                media = requests.get(play_url, timeout=30, stream=True, headers={
                    'User-Agent': self._user_agent,
                })
                media.raise_for_status()
                with open(filename, 'wb') as f:
                    for chunk in media.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                return str(filename), desc or 'TikTok', None
            except Exception as e:
                logger.debug(f"Secondary API {api['name']} failed: {e}")
        
        return None, None, None

    @property
    def _user_agent(self):
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    async def download(self, url: str) -> tuple[bool, list, str]:
        """Download TikTok media"""
        try:
            return await self._download_with_retry(url)
        except ValueError as e:
            return False, [], str(e)
        except Exception as e:
            logger.error(f"Unexpected error in TikTok download: {e}")
            return False, [], "❌ فشل التحميل من TikTok"

    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        """Convert technical errors to user-friendly messages"""
        if not error:
            return "❌ فشل التحميل من TikTok. حاول مرة أخرى."
        
        logger.warning(f"TikTok download failed: {error[:150]}")
        
        error_lower = error.lower()
        
        error_messages = {
            'cookie': "❌ يحتاج TikTok لـ cookies. أضف cookies في cookies_tiktok.txt أو data/cookies_tiktok.txt\n📖 استخدم إضافة 'Get cookies.txt LOCALLY' من متصفحك",
            '403': "❌ المحتوى محظور في منطقتك أو يحتاج لـ cookies",
            'forbidden': "❌ المحتوى محظور في منطقتك",
            'banned': "❌ المحتوى محظور في منطقتك",
            '404': "❌ المحتوى غير موجود أو تم حذفه",
            'private': "❌ المحتوى خاص وغير متاح للجمهور",
            'live': "❌ المحتوى المباشر غير مدعوم",
            'timeout': "❌ انتهت مهلة التحميل. جرب مرة أخرى.",
            'network': "❌ مشكلة في الاتصال. تحقق من الإنترنت.",
            'unavailable': "❌ المحتوى غير متاح للتحميل",
            'region': "❌ المحتوى غير متاح في منطقتك",
            'تسجيل الدخول': "❌ يحتاج TikTok لـ cookies",
            'تأكيد': "❌ TikTok يتطلب تأكيد. أضف cookies",
            'watermark': "❌ لا يمكن إزالة العلامة المائية",
        }
        
        for key, message in error_messages.items():
            if key in error_lower:
                return message
        
        if 'login' in error_lower or 'sign in' in error_lower:
            return "❌ يحتاج TikTok لـ cookies. أضف cookies في cookies_tiktok.txt\n📖 استخدم إضافة 'Get cookies.txt LOCALLY' من متصفحك"
        
        if 'api' in error_lower or 'rate' in error_lower:
            return "❌ TikTok حد من طلباتك. انتظر قليلاً ثم حاول مرة أخرى."
        
        return "❌ فشل التحميل من TikTok. تأكد من الرابط وحاول مرة أخرى."

    async def check_url_valid(self, url: str) -> Tuple[bool, str]:
        """Check if TikTok URL is valid and supported"""
        try:
            url = self._normalize_url(url)
            
            patterns = [
                r'tiktok\.com/@[\w.-]+/video/\d+',
                r'tiktok\.com/@[\w.-]+/photo/\d+',
                r'vm\.tiktok\.com/',
                r'vt\.tiktok\.com/',
                r'tiktok\.com/t/',
                r'tiktok\.com/[\w.-]+/video/\d+',
                r'tiktok\.com/[\w.-]+/photo/\d+',
            ]
            
            if not any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns):
                return False, "❌ نوع هذا الرابط غير مدعوم"
            
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
                    'title': info.get('title') or info.get('description') or 'TikTok',
                    'uploader': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'share_count': info.get('share_count'),
                    'upload_date': info.get('upload_date'),
                    'duration': info.get('duration'),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting media info: {e}")
            return None
