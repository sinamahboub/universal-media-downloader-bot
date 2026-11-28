"""
Production-grade Telegram Media Downloader Bot.

Main entry point with full async architecture, single-instance lock,
graceful shutdown, and comprehensive error handling.
"""

import logging
import re
import sys

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.handlers.callback import CallbackQueryHandler as BotCallbackQueryHandler
from bot.handlers.message import MessageHandler as BotMessageHandler
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.services.media_service import MediaDownloadService
from core.config import get_settings
from core.exceptions import ConfigurationError
from core.logger import StructuredLogger
from infrastructure.lock import ensure_single_instance
from infrastructure.queue import AsyncDownloadQueue
from infrastructure.storage import StorageManager

struct_logger = StructuredLogger(component="main")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, get_settings().LOG_LEVEL.upper()),
)
logger = logging.getLogger(__name__)

# Telegram bot tokens look like "<bot-id>:<secret>", e.g.
# "123456789:AAE..." with a 35-character secret. This only checks the
# shape, never the network: a malformed token fails fast with a clear
# message instead of a confusing API error at polling time.
_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")


def validate_token(token: str) -> None:
    """Validate the bot token shape, raising ConfigurationError."""
    if not token:
        raise ConfigurationError(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env "
            "and set TELEGRAM_BOT_TOKEN to the token from @BotFather."
        )
    if not _TOKEN_RE.match(token):
        raise ConfigurationError(
            "TELEGRAM_BOT_TOKEN does not look like a Telegram bot token "
            "(expected '<bot-id>:<secret>'). Check the value in .env."
        )


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
    """Handle /cancel command (legacy fallback).

    The registered /cancel handler is MessageHandler.handle_cancel,
    which cancels the user's downloads for real. This function is
    kept only so the old name still resolves.
    """
    if update.message is not None:
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


def _guarded(handler, auth: AuthMiddleware):
    """Wrap a command handler with the auth check.

    python-telegram-bot has no middleware chain, so guards are applied
    explicitly. Rate limiting is applied only to the download entry
    points (messages and callbacks), not to /start and /help.
    """

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await auth.check(update, context):
            return
        await handler(update, context)

    return wrapper


async def _post_init(app: Application) -> None:
    """Run once after the application is built, before polling.

    Deletes any stale webhook (the bot polls) and validates the token
    against Telegram with getMe, so a bad token fails here with a
    clear message instead of dying mid-polling.
    """
    await _safe_delete_webhook(app)
    await _validate_token(app)


async def _safe_delete_webhook(app: Application) -> None:
    """Delete webhook without raising on network errors."""
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted successfully")
    except TelegramError as exc:
        logger.warning("delete_webhook_failed: %s", exc)
    except Exception as exc:
        logger.warning("delete_webhook_unexpected_error: %s", exc)


async def _validate_token(app: Application) -> None:
    """Validate bot token by calling getMe.

    Raises:
        ConfigurationError: If the token is rejected by Telegram.
    """
    try:
        me = await app.bot.get_me()
        logger.info("bot_authenticated: id=%s username=%s", me.id, me.username)
    except Exception as exc:
        # Any getMe failure -- a rejected token (TelegramError) or
        # no route to Telegram at all -- is a startup failure with
        # the same clear message. PTB's bootstrap retry loop would
        # otherwise surface the raw httpx error.
        raise ConfigurationError(
            f"Could not validate the bot token with Telegram (getMe failed: {exc}). "
            "Check TELEGRAM_BOT_TOKEN in .env and the network connection."
        ) from exc


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    import shutil
    return shutil.which("ffmpeg") is not None


def create_bot_application() -> Application:
    """Create and configure the Telegram bot application.

    Raises:
        ConfigurationError: If the bot token is missing or malformed.
    """
    settings = get_settings()
    validate_token(settings.TELEGRAM_BOT_TOKEN)

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

    # Auth and rate limiting are wired here explicitly: PTB has no
    # middleware chain, so the handler classes run these checks at the
    # top of every update (previously the middleware classes existed
    # but were never instantiated, so ALLOWED_USERS had no effect).
    auth = AuthMiddleware()
    rate_limit = RateLimitMiddleware()

    message_handler = BotMessageHandler(
        media_service=media_service, auth=auth, rate_limit=rate_limit
    )
    callback_handler = BotCallbackQueryHandler(
        media_service=media_service, auth=auth, rate_limit=rate_limit
    )

    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", _guarded(start_command, auth)))
    application.add_handler(CommandHandler("help", _guarded(help_command, auth)))
    # /cancel goes through the message handler so it cancels the
    # user's pending/running downloads for real.
    application.add_handler(CommandHandler("cancel", message_handler.handle_cancel))

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


def _is_network_error(exc: BaseException) -> bool:
    """True when an exception is a failure to reach Telegram.

    PTB's own ``bot.initialize()`` calls getMe before our post_init
    runs, so a bad token or an unreachable Telegram surfaces here
    as a telegram NetworkError or a raw httpx error, not as our
    ConfigurationError. Both mean the same thing to the operator.
    """
    if isinstance(exc, TelegramError):
        return True
    return type(exc).__module__.split(".")[0] == "httpx"


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
    except ConfigurationError as exc:
        print(f"Bot failed to start: {exc}")
        sys.exit(1)
    except Exception as exc:
        if _is_network_error(exc):
            print(
                "Bot failed to start: could not reach Telegram to "
                "validate the bot token. Check TELEGRAM_BOT_TOKEN in "
                f".env and the network connection. ({exc})"
            )
        else:
            logger.error("bot_startup_failed: %s", exc, exc_info=True)
            print(f"Bot failed to start: {exc}")
        sys.exit(1)
    finally:
        print("Cleaning up...")
        lock.release()
        print("Shutdown complete")


if __name__ == "__main__":
    main()
