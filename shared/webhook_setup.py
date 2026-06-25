"""
Webhook setup for Telegram bot integration into Flask web server.
Uses a background thread with persistent event loop to avoid
"Event loop is closed" errors when processing updates from Flask.
"""
import asyncio
import logging
import os
import sys
import threading
import queue as queue_module
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update

from config.settings import settings
from bot.handlers.main_handlers import router as main_router
from bot.utils.rate_limiter import get_rate_limiter
from bot.utils.database import init_database

logger = logging.getLogger(__name__)

_bot: Bot = None
_dp: Dispatcher = None
_rate_limiter = None
_initialized = False
_queue_manager = None

_loop: asyncio.AbstractEventLoop = None
_loop_thread: threading.Thread = None
_update_queue: queue_module.Queue = None
_init_event: threading.Event = None

admin_router = None
try:
    from bot.handlers.admin_handlers import admin_router as ar
    admin_router = ar
except ImportError:
    pass

PRIORITY_QUEUE_ENABLED = False
try:
    from bot.utils.priority_queue import init_queue_manager as iqm, get_queue_manager as gqm
    PRIORITY_QUEUE_ENABLED = True
except ImportError:
    iqm = None
    gqm = None


def get_bot() -> Bot:
    return _bot


def get_dispatcher() -> Dispatcher:
    return _dp


def _bot_thread_main():
    """Main function for the background thread that runs the bot's event loop"""
    global _bot, _dp, _rate_limiter, _queue_manager, _initialized, _loop

    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    try:
        _loop.run_until_complete(_async_bot_init())
    except Exception as e:
        logger.error(f"Bot thread initialization failed: {e}")
        _init_event.set()
        return

    _init_event.set()
    _loop.run_forever()

    logger.info("Bot event loop stopped")


async def _async_bot_init():
    global _bot, _dp, _rate_limiter, _queue_manager, _initialized

    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set")
        return

    db_path = os.getenv("DB_PATH", "bot_data.db")
    await init_database(db_path)
    logger.info("Database initialized")

    _rate_limiter = get_rate_limiter()
    await _rate_limiter.start_cleanup_task()
    logger.info("Rate limiter started")

    _bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    _dp = Dispatcher()
    if admin_router:
        _dp.include_router(admin_router)
    _dp.include_router(main_router)

    if PRIORITY_QUEUE_ENABLED and iqm:
        try:
            _queue_manager = iqm(
                max_concurrent=3,
                max_queue=100,
                timeout=300,
                enable_points=True
            )
            await _queue_manager.start()
            _queue_manager.load_all_data()
            logger.info("Priority queue initialized")
        except Exception as e:
            logger.error(f"Priority queue error: {e}")

    _initialized = True

    asyncio.create_task(_process_update_queue())
    asyncio.create_task(_check_reload_signal())
    logger.info("Bot initialized successfully in background thread")


async def _check_reload_signal():
    """Check WordPress reload signal file periodically"""
    signal_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'reload.signal')
    os.makedirs(os.path.dirname(signal_file), exist_ok=True)
    last_check = 0
    while True:
        try:
            if os.path.exists(signal_file):
                mtime = os.path.getmtime(signal_file)
                if mtime > last_check:
                    last_check = mtime
                    from config.settings import get_wp_option
                    new_token = get_wp_option('tk_bot_token', '')
                    if new_token and new_token != settings.BOT_TOKEN:
                        logger.info("Bot token updated from WordPress")
                        settings.BOT_TOKEN = new_token
                    logger.info("Settings reloaded from WordPress signal")
        except Exception as e:
            logger.debug(f"Reload check: {e}")
        await asyncio.sleep(30)


async def _process_update_queue():
    """Continuously process updates from the queue"""
    logger.info("Update processor started")
    while True:
        try:
            update_data = await asyncio.get_event_loop().run_in_executor(
                None, _update_queue.get
            )
            if update_data is None:
                break

            try:
                update = Update.model_validate(update_data)
                await _dp.feed_update(_bot, update)
            except Exception as e:
                logger.error(f"Error processing update: {e}")

        except Exception as e:
            logger.error(f"Queue processor error: {e}")
            await asyncio.sleep(1)

    logger.info("Update processor stopped")


def setup_bot():
    """Initialize bot in a background thread with persistent event loop.
    Returns True if bot started successfully, False otherwise."""
    global _loop_thread, _update_queue, _init_event

    if _initialized:
        logger.info("Bot already initialized")
        return True

    logger.info("Starting bot in background thread...")

    _update_queue = queue_module.Queue()
    _init_event = threading.Event()

    _loop_thread = threading.Thread(
        target=_bot_thread_main,
        daemon=True,
        name="bot-loop"
    )
    _loop_thread.start()

    _init_event.wait(timeout=30)

    if not _initialized:
        logger.error("Bot initialization timed out or failed")
        return False

    logger.info("Bot background thread started successfully")
    return True


def _run_on_loop(coro, timeout=15):
    """Run a coroutine on the bot's event loop thread-safely"""
    if not _loop or _loop.is_closed():
        logger.error("Bot event loop not running")
        return None
    try:
        future = asyncio.run_coroutine_threadsafe(coro, _loop)
        return future.result(timeout=timeout)
    except Exception as e:
        logger.error(f"Error running on bot loop: {e}")
        return None


def set_webhook(url: str):
    """Set the webhook URL on Telegram's API (thread-safe)"""
    async def _set():
        if not _bot:
            return False
        try:
            result = await _bot.set_webhook(
                url=url,
                allowed_updates=["message", "callback_query"]
            )
            if result:
                logger.info(f"Webhook set to: {url}")
            else:
                logger.error(f"Failed to set webhook: {url}")
            return result
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False

    return _run_on_loop(_set()) or False


def process_update(update_data: dict):
    """Push an incoming Telegram update to the background queue (non-blocking)"""
    if not _initialized:
        logger.warning("Bot not initialized, skipping update")
        return
    _update_queue.put(update_data)


def shutdown_bot():
    """Shutdown the bot and background event loop"""
    global _initialized, _loop

    if not _initialized:
        return

    logger.info("Shutting down bot...")

    async def _shutdown():
        if _queue_manager:
            try:
                _queue_manager.save_all_data()
                await _queue_manager.stop()
            except:
                pass
        if _rate_limiter:
            try:
                await _rate_limiter.stop_cleanup_task()
            except:
                pass
        if _bot:
            try:
                await _bot.session.close()
            except:
                pass

    _run_on_loop(_shutdown(), timeout=10)

    if _loop and not _loop.is_closed():
        _loop.call_soon_threadsafe(lambda: _update_queue.put(None))
        _loop.call_soon_threadsafe(_loop.stop)
        _loop_thread.join(timeout=5)
        try:
            _loop.close()
        except:
            pass

    _initialized = False
    logger.info("Bot shut down")
