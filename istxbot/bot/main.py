"""
istxbot - Telegram Bot for downloading content from 9 platforms

Copyright (c) 2025 Abdulmajeed Alarmani
License: MIT
"""

import asyncio
import logging
import sys
import os
import signal
from pathlib import Path
from logging.handlers import RotatingFileHandler

sys.path.append(str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config.settings import settings

from bot.handlers.main_handlers import router as main_router
from bot.utils.rate_limiter import get_rate_limiter
from bot.utils.database import init_database
from bot.utils.exceptions import get_dead_letter_queue, StructuredLogger
from bot.utils.cryptomanager import get_crypto_manager

# تعريف المتغيرات بالقيم الافتراضية
admin_router = None
init_queue_manager = None
get_queue_manager = None
UserTier = None
PRIORITY_QUEUE_ENABLED = False

# متغير عام للوصول إلى bot
_bot_instance = None

def get_bot():
    """الحصول على bot instance"""
    return _bot_instance

try:
    from bot.handlers.admin_handlers import admin_router as admin_router_imported
    admin_router = admin_router_imported
    logging.info("✅ Admin handlers loaded")
except ImportError:
    admin_router = None
    logging.warning("Admin handlers not imported")

try:
    from bot.utils.priority_queue import (
        init_queue_manager as init_queue_manager_imported,
        get_queue_manager as get_queue_manager_imported,
        UserTier as UserTier_imported
    )
    init_queue_manager = init_queue_manager_imported
    get_queue_manager = get_queue_manager_imported
    UserTier = UserTier_imported
    PRIORITY_QUEUE_ENABLED = True
    logging.info("✅ Priority queue module loaded")
except ImportError as e:
    PRIORITY_QUEUE_ENABLED = False
    logging.warning(f"⚠️ Priority queue not available: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'bot.log', maxBytes=10*1024*1024, backupCount=5,
            encoding='utf-8'
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
structured_logger = StructuredLogger("main", get_dead_letter_queue())

class BotRunner:
    def __init__(self):
        self.bot = None
        self.dp = None
        self.should_run = True
        
    async def setup(self):
        try:
            structured_logger.log_info("Initializing bot setup...")
            
            if not settings.BOT_TOKEN:
                error_msg = "❌ BOT_TOKEN is not set in .env file"
                logger.error(error_msg)
                return False
            
            structured_logger.log_info("Initializing encryption manager...")
            crypto_manager = get_crypto_manager()
            logger.info("✅ Encryption manager initialized")
            
            structured_logger.log_info("Initializing database...")
            db_path = os.getenv("DB_PATH", "bot_data.db")
            await init_database(db_path)
            logger.info(f"✅ Database initialized: {db_path}")
            
            structured_logger.log_info("Initializing rate limiter...")
            self.rate_limiter = get_rate_limiter()
            await self.rate_limiter.start_cleanup_task()
            logger.info("✅ Rate limiter started")
            
            self.bot = Bot(
                token=settings.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            global _bot_instance
            _bot_instance = self.bot
            
            self.dp = Dispatcher()
            if admin_router:
                self.dp.include_router(admin_router)
                logger.info("✅ Admin handlers loaded")
            self.dp.include_router(main_router)
            if PRIORITY_QUEUE_ENABLED and init_queue_manager:
                self.queue_manager = init_queue_manager(
                    max_concurrent=3,
                    max_queue=100,
                    timeout=300,
                    enable_points=True
                )
                await self.queue_manager.start()
                self.queue_manager.load_all_data()
                logger.info("✅ Priority queue initialized and started")
                logger.info("✅ Data loaded from files")
            else:
                self.queue_manager = None
                logger.info("⚠️ Priority queue not enabled")
            
            logger.info("✅ Bot initialized successfully")
            return True
            
        except Exception as e:
            structured_logger.log_error(e, include_traceback=True)
            logger.error(f"❌ Setup failed: {e}")
            return False
        
    async def start_polling(self):
        logger.info("🤖 Bot is starting...")
        logger.info(f"👤 Admin ID: {settings.ADMIN_ID if settings.ADMIN_ID else 'Not set'}")
        logger.info(f"📁 Download dir: {settings.DOWNLOAD_DIR}")
        
        if self.queue_manager:
            logger.info("📊 Priority queue is active")
        
        if not self.bot or not self.dp:
            logger.error("❌ Bot or dispatcher not initialized")
            return
            
        try:
            await self.dp.start_polling(
                self.bot, 
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            logger.error(f"❌ Error during polling: {e}")
        finally:
            await self.shutdown()
            
    async def shutdown(self):
        logger.info("🛑 Shutting down bot...")
        
        try:
            if self.queue_manager:
                logger.info("📊 Stopping priority queue...")
                try:
                    self.queue_manager.save_all_data()
                    logger.info("✅ Data saved to files")
                    await self.queue_manager.stop()
                    logger.info("✅ Priority queue stopped")
                except Exception as e:
                    logger.error(f"Error stopping queue: {e}")
            
            if hasattr(self, 'rate_limiter'):
                logger.info("🛡️ Stopping rate limiter...")
                await self.rate_limiter.stop_cleanup_task()
                logger.info("✅ Rate limiter stopped")
            
            if self.bot:
                await self.bot.session.close()
            
            logger.info("✅ Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            structured_logger.log_error(e, include_traceback=True)
        
    def setup_signal_handlers(self):
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, 
                lambda: asyncio.create_task(self.shutdown())
            )

async def main():
    runner = BotRunner()
    
    if not await runner.setup():
        return
        
    runner.setup_signal_handlers()
    
    logger.info("🔒 Security systems active:")
    logger.info("  • URL Validation - Enabled")
    logger.info("  • Encryption - Enabled")
    logger.info("  • Rate Limiting - Enabled")
    logger.info("  • Structured Logging - Enabled")
    logger.info("  • Database - SQLite")
    
    if PRIORITY_QUEUE_ENABLED and runner.queue_manager:
        logger.info("📊 Priority queue system is running")
        logger.info("👑 Users can use: /queue, /leaderboard, /points, /tier, /cancel")
    
    await runner.start_polling()

def run_daemon():
    pid = os.fork()
    if pid > 0:
        print(f"✅ Bot is running in background (PID: {pid})")
        sys.exit(0)
    elif pid == 0:
        os.setsid()
        asyncio.run(main())
    else:
        print("❌ Failed to start daemon")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram Download Bot")
    parser.add_argument(
        '--daemon', 
        action='store_true',
        help='Run bot in background'
    )
    parser.add_argument(
        '--stop',
        action='store_true',
        help='Stop running bot'
    )
    
    args = parser.parse_args()
    
    if args.stop:
        os.system("pkill -f 'python3 bot/main.py'")
        print("✅ Bot stopped")
    elif args.daemon:
        run_daemon()
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("👋 Bot stopped by user")
