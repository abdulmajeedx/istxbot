import asyncio

import logging
import re
import shutil

from typing import Optional, Tuple
from config.settings import settings

logger = logging.getLogger(__name__)

class SpotifyDownloader:
    def __init__(self):
        self.download_dir = settings.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._max_retries = 2
        self._base_delay = 2.0
        
        self._check_spotdl_installed()

    def _check_spotdl_installed(self):
        if not shutil.which('spotdl'):
            logger.warning("⚠️ spotdl not found in PATH. Spotify downloads may not work.")

    def _extract_track_info(self, url: str) -> Optional[str]:
        if 'open.spotify.com' not in url:
            return None
        
        match = re.search(r'track/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        
        match = re.search(r'album/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        
        match = re.search(r'playlist/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        
        return None

    async def _execute_spotdl(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        output_dir = str(self.download_dir)
        cmd = ['spotdl', 'download', url, '--output-dir', output_dir, '--format', 'mp3']
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.DOWNLOAD_TIMEOUT
                )
                
                if process.returncode != 0:
                    error_output = stderr.decode('utf-8', errors='ignore')
                    return False, None, error_output
                
                return await self._find_downloaded_file()
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return False, None, "انتهت مهلة التحميل. الأغنية قد تكون طويلة جداً."
                
        except FileNotFoundError:
            return False, None, "❌ خطأ في خدمة التحميل. حاول مرة أخرى."
        except Exception as e:
            logger.error(f"Error executing spotdl: {e}")
            return False, None, "❌ فشل التحميل. حاول مرة أخرى."

    async def _find_downloaded_file(self) -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            await asyncio.sleep(1)
            
            mp3_files = list(self.download_dir.glob('*.mp3'))
            
            if not mp3_files:
                return False, None, "لم يتم العثور على ملف MP3 بعد التحميل"
            
            latest_file = max(mp3_files, key=lambda p: p.stat().st_mtime)
            
            if latest_file.exists() and latest_file.stat().st_size > 0:
                title = latest_file.stem
                return True, str(latest_file), title
            
            return False, None, "الملف فارغ أو تالف"
            
        except Exception as e:
            logger.error(f"Error finding downloaded file: {e}")
            return False, None, "❌ فشل التحميل. حاول مرة أخرى."

    async def download_with_retry(self, url: str) -> Tuple[bool, str, str]:
        track_id = self._extract_track_info(url)
        
        if not track_id:
            return False, "", "❌ الرابط غير صحيح. تأكد من إرسال رابط Spotify صحيح."
        
        last_error: Optional[str] = None
        
        for attempt in range(self._max_retries):
            try:
                success, filename, title = await self._execute_spotdl(url)
                
                if success and filename:
                    return True, filename, title
                
                last_error = title
                
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Spotify download attempt {attempt + 1} failed: {last_error}")
        
        error_msg = self._get_user_friendly_error(last_error)
        return False, "", error_msg

    async def download(self, url: str) -> tuple[bool, str, str]:
        return await self.download_with_retry(url)

    def _get_user_friendly_error(self, error: Optional[str]) -> str:
        if not error:
            return "فشل التحميل بسبب غير معروف"
        
        error_lower = error.lower()
        
        if 'not found' in error_lower or 'track not found' in error_lower:
            return "❌ الأغنية غير موجودة. تحقق من الرابط."
        elif 'region' in error_lower or 'unavailable' in error_lower:
            return "❌ هذا المحتوى غير متاح في منطقتك."
        elif 'private' in error_lower:
            return "❌ هذا المحتوى خاص ولا يمكن تحميله."
        elif 'premium' in error_lower:
            return "❌ يتطلب حساب Spotify Premium."
        elif 'timeout' in error_lower:
            return "❌ انتهت مهلة التحميل. جرب رابط أغنية واحدة."
        elif 'spotdl' in error_lower and 'not found' in error_lower:
            return "❌ spotdl غير مثبت. تحقق من التثبيت."
        
        return "❌ فشل التحميل. حاول مرة أخرى."


