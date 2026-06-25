"""
@istxbot Settings — reads from .env file
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from istxbot/.env or fallback to cwd
_env_path = Path(__file__).parent.parent / '.env'
load_dotenv(_env_path)
load_dotenv()


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
    DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT", "300"))
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "ffmpeg")
    DOWNLOAD_DIR: Path = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
    BOT_API_KEY: str = os.getenv("BOT_API_KEY", "")
    DEV_MODE: bool = os.getenv("DEV_MODE", "false").lower() == "true"

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        admin_str = str(self.ADMIN_ID)
        admins = [x.strip() for x in admin_str.split(',') if x.strip()]
        return str(user_id) in admins or user_id == self.ADMIN_ID


settings = Settings()
