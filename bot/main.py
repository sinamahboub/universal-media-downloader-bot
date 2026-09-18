"""
Production-grade Telegram Media Downloader Bot.

Main entry point with full async architecture, single-instance lock,
graceful shutdown, and comprehensive error handling.
"""

import logging
import sys
import asyncio
from pathlib import Path

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from core.config import settings
from core.logger import StructuredLogger
from infrastructure.queue import AsyncDownloadQueue
from infrastructure.storage import StorageManager
from infrastructure.lock import ensure_single_instance

from bot.handlers.callback import CallbackQueryHandler as BotCallbackQueryHandler
from bot.handlers.message import MessageHandler as BotMessageHandler
from bot.services.media_service import MediaDownloadService

struct_logger = StructuredLogger(component="main")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, settings.LOG_LEVEL.upper()),
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "Welcome! Send me a URL from YouTube, SoundCloud, or Instagram."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "Send me a media URL and I'll download it for you."
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command."""
    if "pending_url" in context.user_data:
        del context.user_data["pending_url"]
    await update.message.reply_text("Cancelled.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler."""
    logger.error("Bot error", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "An error occurred. Please try again."
            )
        except Exception:
            pass


async def _safe_delete_webhook(app: Application) -> None:
    """Delete webhook without raising on network errors."""
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted successfully")
    except TelegramError as exc:
        logger.warning("delete_webhook_failed: %s", exc)
    except Exception as exc:
        logger.warning("delete_webhook_unexpected_error: %s", exc)


async def _safe_get_me(app: Application) -> None:
    """Validate bot token by calling getMe."""
    try:
        me = await app.bot.get_me()
        logger.info("bot_authenticated: id=%s username=%s", me.id, me.username)
    except TelegramError as exc:
        logger.error("get_me_failed: %s", exc, exc_info=True)
        raise SystemExit(f"Invalid bot token or network issue: {exc}")


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    import shutil
    return shutil.which("ffmpeg") is not None


def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        sys.exit(1)

    ffmpeg_available = check_ffmpeg()
    if not ffmpeg_available:
        logger.warning("ffmpeg_not_found: Downloads will use original format")

    download_queue = AsyncDownloadQueue()
    storage_manager = StorageManager()

    media_service = MediaDownloadService(
        download_queue=download_queue,
        storage_manager=storage_manager,
        ffmpeg_available=ffmpeg_available,
    )

    message_handler = BotMessageHandler(media_service=media_service)
    callback_handler = BotCallbackQueryHandler(media_service=media_service)

    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    application.add_handler(
        MessageHandler(
            filters=filters.TEXT & ~filters.COMMAND,
            callback=message_handler.handle_message,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callback_handler.handle_format_selection,
            pattern=r"^fmt:(audio|video):[a-f0-9-]+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            callback_handler.handle_quality_selection,
            pattern=r"^qual:(best|1080p|720p|480p):[a-f0-9-]+$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            callback_handler.handle_cancel,
            pattern=r"^cancel:[a-f0-9-]+$",
        )
    )

    application.add_error_handler(error_handler)

    return application


def main() -> None:
    """Main entry point for the bot."""
    print("Starting Telegram Media Downloader Bot...")

    lock = ensure_single_instance()
    print(f"Single instance lock acquired (PID: {lock.pid})")

    try:
        app = create_bot_application()
        print("Bot configured successfully")
        print("Starting polling...")
        print("Press Ctrl+C to stop")

        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as exc:
        logger.error("bot_startup_failed: %s", exc, exc_info=True)
        print(f"Bot failed to start: {exc}")
        sys.exit(1)
    finally:
        print("Cleaning up...")
        lock.release()
        print("Shutdown complete")


if __name__ == "__main__":
    main()

