import yt_dlp
import asyncio
import logging
import random
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from config.settings import settings
from bot.utils.helpers import sanitize_filename, download_with_retry

logger = logging.getLogger(__name__)

class InstagramDownloader:
    def __init__(self):
        self.download_dir = settings.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._max_retries = 5
        self._base_delay = 2.0
        
        # Try multiple cookie file locations (in order of priority)
        base_dir = Path(__file__).parent.parent.parent
        cookies_paths = [
            base_dir / 'cookies_instagram.txt',
            base_dir / 'data' / 'cookies_instagram.txt',
            base_dir / 'cookies.txt',
            base_dir / 'data' / 'cookies.txt'
        ]
        
        self._cookies_file = None
        for path in cookies_paths:
            if path.exists():
                content = path.read_text().strip()
                # Check if file has actual cookies (not just comments)
                if content and not (content.startswith('#') and len(content) < 100):
                    self._cookies_file = path
                    logger.info(f"Using Instagram cookies from: {path}")
                    break
        
        if not self._cookies_file:
            logger.warning("No valid Instagram cookies file found")
        
    def _get_random_user_agent(self) -> str:
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        return random.choice(user_agents)
    
    def _extract_shortcode(self, url: str) -> Optional[str]:
        url = url.strip().rstrip('/')
        
        if '/p/' in url:
            parts = url.split('/p/')
            return parts[1].split('/')[0] if len(parts) > 1 else None
        elif '/reel/' in url:
            parts = url.split('/reel/')
            return parts[1].split('/')[0] if len(parts) > 1 else None
        elif '/tv/' in url:
            parts = url.split('/tv/')
            return parts[1].split('/')[0] if len(parts) > 1 else None
        
        return None

    def _get_ydl_options(self, output_path: str) -> Dict[str, Any]:
        options = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'{output_path}/%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'user_agent': self._get_random_user_agent(),
            'http_headers': {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'extract_flat': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'timeout': 60,
        }
        
        if self._cookies_file and self._cookies_file.exists():
            options['cookiefile'] = str(self._cookies_file)
            logger.info("Using cookies file for Instagram")
        
        return options

    async def _download_post(self, url: str) -> Dict[str, Any]:
        output_path = str(self.download_dir)
        ydl_opts = self._get_ydl_options(output_path)
        
        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if not info:
                        return {
                            'success': False,
                            'error': 'لم يتم العثور على معلومات الفيديو'
                        }
                    
                    files = []
                    
                    if 'entries' in info:
                        for entry in info['entries']:
                            if entry:
                                filename = ydl.prepare_filename(entry)
                                if Path(filename).exists():
                                    files.append(filename)
                    else:
                        filename = ydl.prepare_filename(info)
                        if Path(filename).exists():
                            files.append(filename)
                    
                    title = info.get('title', 'Instagram Media')
                    description = info.get('description', '')
                    
                    if '/p/' in url:
                        media_type = 'Instagram Post'
                    elif '/reel/' in url:
                        media_type = 'Instagram Reel'
                    elif '/tv/' in url:
                        media_type = 'Instagram IGTV'
                    else:
                        media_type = 'Instagram Media'
                    
                    caption = description if description else title
                    
                    return {
                        'success': True,
                        'files': files,
                        'caption': caption,
                        'media_type': media_type
                    }
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if '403' in error_msg or 'Forbidden' in error_msg:
                    return {
                        'success': False,
                        'error': '❌ تم حظر الوصول. قد يكون المحتوى خاص.'
                    }
                elif '404' in error_msg or 'Not Found' in error_msg:
                    return {
                        'success': False,
                        'error': '❌ المنشور غير موجود أو تم حذفه.'
                    }
                elif '429' in error_msg or 'rate limit' in error_msg.lower():
                    return {
                        'success': False,
                        'error': '❌ تم الوصول للحد الأقصى. انتظر بضع دقائق.'
                    }
                elif 'cookies' in error_msg.lower() or 'login required' in error_msg.lower():
                    logger.warning(f"Instagram login required: {error_msg[:100]}")
                    return {
                        'success': False,
                        'error': 'فشل التحميل. حاول مرة أخرى.'
                    }
                return {
                    'success': False,
                    'error': 'فشل التحميل. حاول مرة أخرى.'
                }
            except Exception as e:
                logger.error(f"Error downloading Instagram post: {e}")
                return {
                    'success': False,
                    'error': '❌ فشل التحميل. حاول مرة أخرى.'
                }
        
        return await asyncio.get_event_loop().run_in_executor(None, _download)

    async def download_with_retry(self, url: str) -> Tuple[bool, List[str], str]:
        if not self._extract_shortcode(url):
            return False, [], "❌ الرابط غير صحيح. تأكد من إرسال رابط Instagram صحيح."
        
        last_error = None
        
        for attempt in range(self._max_retries):
            try:
                result = await self._download_post(url)
                
                if result['success']:
                    files = result['files']
                    caption = result['caption']
                    media_type = result['media_type']
                    
                    valid_files = []
                    for f in files:
                        if Path(f).exists():
                            valid_files.append(f)
                    
                    if valid_files:
                        full_caption = f"{media_type}: {caption[:100]}" if caption else media_type
                        return True, valid_files, sanitize_filename(full_caption)
                    
                    last_error = "لم يتم العثور على ملفات بعد التحميل"
                else:
                    last_error = result['error']
                
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Instagram download attempt {attempt + 1} failed: {last_error}")
        
        error_msg = self._get_user_friendly_error(last_error)
        return False, [], error_msg

    async def download(self, url: str) -> Tuple[bool, List[str], str]:
        return await self.download_with_retry(url)

    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        if not error:
            return "فشل التحميل. حاول مرة أخرى."
        
        if "تتطلب تسجيل الدخول" in error or "LoginRequired" in error or "private" in error.lower() or "cookies" in error.lower():
            logger.warning(f"Instagram requires cookies: {error[:100]}")
            return "فشل التحميل. حاول مرة أخرى."
        elif "غير موجود" in error or "Not Found" in error or "404" in error:
            logger.warning(f"Instagram content not found: {error[:100]}")
            return "فشل التحميل. حاول مرة أخرى."
        elif "تم حظره" in error or "blocked" in error.lower() or "403" in error or "Forbidden" in error:
            logger.warning(f"Instagram rate limit/blocked: {error[:100]}")
            return "فشل التحميل. حاول مرة أخرى."
        elif "الحد الأقصى" in error or "429" in error or "rate limit" in error.lower():
            logger.warning(f"Instagram rate limit: {error[:100]}")
            return "فشل التحميل. حاول مرة أخرى."
        
        logger.error(f"Instagram download failed: {error[:100]}")
        return "فشل التحميل. حاول مرة أخرى."
