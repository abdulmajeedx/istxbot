import asyncio
import logging
import hashlib
import time
import re
import os
from pathlib import Path

import requests
from config.settings import settings

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

logger = logging.getLogger(__name__)

class PinterestDownloader:
    def __init__(self):
        self.download_dir = settings.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._max_retries = 2
        self._base_delay = 1.0
        
        self.apis = [
            # Place the most stable endpoints first
            'https://pinterestvideodownloader.com/api',
            'https://pinterest-download.com/api',
            'https://pinterestdownloader.com/api/get',
        ]
        
        self.api_cache: Dict[str, Tuple[float, bool]] = {}
        self._cache_ttl = 300

    def _is_valid_pinterest_url(self, url: str) -> bool:
        return 'pinterest.com' in url.lower() or 'pin.it/' in url.lower()

    def _get_api_timeout(self, api_url: str) -> int:
        cache_key = hashlib.md5(api_url.encode()).hexdigest()
        
        if cache_key in self.api_cache:
            timestamp, is_bad = self.api_cache[cache_key]
            
            if is_bad and time.time() - timestamp < self._cache_ttl:
                return 5
            
            if time.time() - timestamp > self._cache_ttl:
                del self.api_cache[cache_key]
        
        return 15

    def _mark_api_as_bad(self, api_url: str):
        cache_key = hashlib.md5(api_url.encode()).hexdigest()
        self.api_cache[cache_key] = (time.time(), True)
        logger.warning(f"Marked API as bad: {api_url}")

    def _mark_api_as_good(self, api_url: str):
        cache_key = hashlib.md5(api_url.encode()).hexdigest()
        self.api_cache[cache_key] = (time.time(), False)

    def _resolve_url(self, url: str) -> str:
        """Expand short pin.it links to full pinterest.com URLs when possible."""
        try:
            if 'pin.it/' not in url.lower():
                return url
            
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=10,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                }
            )
            if response.url:
                return response.url
        except Exception as e:
            logger.warning(f"Failed to resolve short Pinterest URL {url}: {e}")
        return url

    def _scrape_pinterest_page(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Fallback scraper using OG meta tags from the Pinterest page."""
        try:
            resp = requests.get(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                },
                timeout=15,
                allow_redirects=True
            )
            if resp.status_code != 200:
                return False, None, None
            
            html = resp.text
            
            # Try multiple patterns for media extraction
            media_url = None
            ext = 'jpg'
            
            # Pattern 1: OG video tag (standard)
            video_match = re.search(r'property=["\']og:video["\']\s*content=["\']([^"\']+)["\']', html)
            if video_match:
                media_url = video_match.group(1)
                ext = 'mp4'
            
            # Pattern 1b: OG video:secure_url
            if not media_url:
                video_match = re.search(r'property=["\']og:video:secure_url["\']\s*content=["\']([^"\']+)["\']', html)
                if video_match:
                    media_url = video_match.group(1)
                    ext = 'mp4'
            
            # Pattern 1c: Video in JSON data
            if not media_url:
                video_json_match = re.search(r'"video"\s*:\s*\{[^}]*"url"\s*:\s*"([^"]+)"', html)
                if video_json_match:
                    media_url = video_json_match.group(1).replace('\\u002F', '/')
                    ext = 'mp4'
            
            # Pattern 1d: Pinterest video URL patterns
            if not media_url:
                video_patterns = [
                    r'https://v\.pinimg\.com/videos/[^\s"\'>]+',
                    r'https://i\.pinimg\.com/videos/[^\s"\'>]+',
                    r'https://pinimg\.com/video/[^\s"\'>]+\.mp4',
                    r'https://[a-z0-9-]+\.pinimg\.com/videos/[^\s"\'>]+',
                ]
                for pattern in video_patterns:
                    match = re.search(pattern, html)
                    if match:
                        media_url = match.group(0)
                        ext = 'mp4'
                        break
            
            # Pattern 2: OG image tag
            if not media_url:
                image_match = re.search(r'property=["\']og:image["\']\s*content=["\']([^"\']+)["\']', html)
                if image_match:
                    media_url = image_match.group(1)
                    ext = 'jpg'
            
            # Pattern 3: High quality pinimg URLs (clean extraction)
            if not media_url:
                # Extract clean pinimg URLs
                candidates = re.findall(r'https://i\.pinimg\.com/[^"\'>\s\)]+', html)
                # Filter for valid image URLs
                for candidate in candidates:
                    if re.match(r'https://i\.pinimg\.com/\w+/\w+/', candidate):
                        media_url = candidate.split(')')[0].split('"')[0].split("'")[0]
                        ext = 'mp4' if '.mp4' in media_url.lower() else 'jpg'
                        break
            
            # Pattern 4: Data-test pin ID
            if not media_url:
                pin_id_match = re.search(r'"id"\s*:\s*"(\d+)"', html)
                if pin_id_match:
                    pin_id = pin_id_match.group(1)
                    # Try video first
                    for size in ['originals', '1200x', '800x']:
                        path_part = f"{pin_id[:2]}/{pin_id[2:4]}/{pin_id[4:6]}"
                        test_url = f"https://i.pinimg.com/{size}/{path_part}/{pin_id}.mp4"
                        try:
                            test_resp = requests.head(test_url, timeout=5)
                            if test_resp.status_code == 200:
                                media_url = test_url
                                ext = 'mp4'
                                break
                        except:
                            pass
                    # Then try images
                    if not media_url:
                        for size in ['originals', '1200x', '800x', '600x']:
                            path_part = f"{pin_id[:2]}/{pin_id[2:4]}/{pin_id[4:6]}"
                            test_url = f"https://i.pinimg.com/{size}/{path_part}/{pin_id}.jpg"
                            try:
                                test_resp = requests.head(test_url, timeout=5)
                                if test_resp.status_code == 200:
                                    media_url = test_url
                                    break
                            except:
                                pass
            
            if not media_url:
                return False, None, None
            
            # Clean the URL
            media_url = media_url.split('?')[0].split(')')[0]
            
            filename = f"{self.download_dir}/pinterest_{hash(url)}.{ext}"
            
            media_resp = requests.get(
                media_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.pinterest.com/',
                },
                timeout=30,
                stream=True
            )
            media_resp.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in media_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            title_match = re.search(r'property=["\']og:title["\']\s*content=["\']([^"\']+)["\']', html)
            title = title_match.group(1) if title_match else f"Pinterest {ext.upper()}"
            return True, filename, title
        except Exception as e:
            logger.error(f"Error scraping Pinterest page: {e}")
            return False, None, None

    async def _try_api(self, url: str, api_url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            timeout = self._get_api_timeout(api_url)
            
            if timeout < 10:
                logger.info(f"Skipping API with reduced timeout: {api_url}")
                return False, None, None
            
            response = requests.post(
                api_url,
                data={'url': url},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, dict):
                    download_url = data.get('url') or data.get('download_url') or data.get('link') or data.get('media')
                    
                    if download_url:
                        ext = 'mp4' if '.mp4' in download_url.lower() or 'video' in download_url.lower() else 'jpg'
                        filename = f"{self.download_dir}/pinterest_{hash(url)}.{ext}"
                        
                        media_response = requests.get(
                            download_url,
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            },
                            timeout=30,
                            stream=True
                        )
                        media_response.raise_for_status()
                        
                        with open(filename, 'wb') as f:
                            for chunk in media_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        title = data.get('title', data.get('description', f"Pinterest {ext.upper()}"))
                        self._mark_api_as_good(api_url)
                        
                        return True, filename, title
            
            return False, None, None
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for API: {api_url}")
            self._mark_api_as_bad(api_url)
            return False, None, None
        except Exception as e:
            logger.error(f"Error with API {api_url}: {e}")
            self._mark_api_as_bad(api_url)
            return False, None, None

    async def download_with_retry(self, url: str) -> Tuple[bool, str, str]:
        if not self._is_valid_pinterest_url(url):
            return False, "", "❌ الرابط غير صحيح. تأكد من إرسال رابط Pinterest."
        
        # Resolve short URLs first
        url = self._resolve_url(url)
        
        last_error: Optional[str] = None
        
        # Try yt-dlp first for videos (most reliable for Pinterest videos)
        if YTDLP_AVAILABLE:
            try:
                success, filename, title = await self._download_with_ytdlp(url)
                if success and filename and Path(filename).exists():
                    return True, filename, title
            except Exception as e:
                logger.warning(f"yt-dlp failed for Pinterest: {e}")
                last_error = str(e)
        
        # Try APIs
        for attempt in range(self._max_retries):
            for api_url in self.apis:
                try:
                    success, filename, title = await self._try_api(url, api_url)
                    
                    if success and filename and title and Path(filename).exists():
                        return True, filename, title
                    
                except Exception as e:
                    logger.error(f"Error trying API {api_url}: {e}")
                    last_error = "فشل الاتصال بـ Pinterest API"
                    continue
            
            if attempt < self._max_retries - 1:
                delay = self._base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        # Final fallback: scrape the Pinterest page directly
        success, filename, title = await asyncio.to_thread(self._scrape_pinterest_page, url)
        if success and filename and Path(filename).exists():
            return True, filename, title
        
        error_msg = self._get_user_friendly_error(last_error)
        return False, "", error_msg
    
    async def _download_with_ytdlp(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download Pinterest media using yt-dlp"""
        def _download():
            try:
                ydl_opts = {
                    'format': 'bestvideo+bestaudio/best/bestvideo/bestaudio',
                    'outtmpl': str(self.download_dir / 'pinterest_%(id)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'ignoreerrors': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'timeout': 60,
                    'merge_output_format': 'mp4',
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if not info:
                        return False, None, "لم يتم العثور على معلومات"
                    
                    # Check if it's actually a video
                    if info.get('duration') is None and 'video' not in str(info.get('url', '')).lower():
                        return False, None, "ليس فيديو"
                    
                    filename = ydl.prepare_filename(info)
                    
                    # Handle merged files
                    if not os.path.exists(filename):
                        # Try common extensions
                        for ext in ['mp4', 'webm', 'mkv']:
                            alt_name = filename.rsplit('.', 1)[0] + '.' + ext
                            if os.path.exists(alt_name):
                                filename = alt_name
                                break
                    
                    if not os.path.exists(filename):
                        return False, None, "لم يتم تحميل الملف"
                    
                    # Verify it's actually a video file
                    import magic
                    try:
                        mime = magic.from_file(filename, mime=True)
                        if not mime.startswith('video/'):
                            os.remove(filename)
                            return False, None, "ليس ملف فيديو"
                    except:
                        pass
                    
                    title = info.get('title', info.get('description', 'Pinterest Video'))
                    return True, filename, title
                    
            except Exception as e:
                logger.error(f"yt-dlp Pinterest error: {e}")
                return False, None, str(e)
        
        return await asyncio.to_thread(_download)

    async def download(self, url: str) -> tuple[bool, str, str]:
        return await self.download_with_retry(url)

    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        if not error:
            return "عذراً، لا يمكن تحميل من Pinterest حالياً."
        
        error_lower = error.lower()
        
        if 'timeout' in error_lower:
            return "❌ انتهت مهلة الطلب. جرب مرة أخرى لاحقاً."
        elif 'private' in error_lower or 'not found' in error_lower:
            return "❌ هذا المحتوى خاص أو غير موجود."
        
        return "عذراً، لا يمكن تحميل من Pinterest حالياً.\n\n📌 الحلول البديلة:\n1. استخدم موقع pinterest-downloader.com\n2. أو احفظ المحتوى يدوياً من تطبيق Pinterest\n\n💡 نعمل على حل هذه المشكلة قريباً"

