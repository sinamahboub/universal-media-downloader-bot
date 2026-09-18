"""
Main Telegram bot application.

Entry point for the downloader bot.
"""

import asyncio
import signal
import sys
from pathlib import Path

from telegram.ext import ApplicationBuilder, ContextTypes, Update

from core.config import settings
from core.exceptions import ConfigurationError
from core.logger import StructuredLogger, log_error_with_context

from infrastructure.queue import AsyncDownloadQueue
from infrastructure.storage import StorageManager

from bot.downloader import DownloaderFactory
from bot.handlers.callback import CallbackQueryHandler
from bot.handlers.message import MessageHandler
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.services import MediaDownloadService, URLParserService

logger = StructuredLogger(component="main")


class DownloaderBot:
    """
    Main bot application class.
    """

    def __init__(self) -> None:
        self._application = None
        self._queue: AsyncDownloadQueue | None = None
        self._storage: StorageManager | None = None
        self._media_service: MediaDownloadService | None = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize all bot components."""
        logger.info("bot_initializing", app_env=settings.APP_ENV)

        self._validate_config()

        self._queue = AsyncDownloadQueue()
        self._storage = StorageManager()

        url_parser = URLParserService()
        self._media_service = MediaDownloadService(
            queue=self._queue,
            storage=self._storage,
            url_parser=url_parser,
        )

        message_handler = MessageHandler(url_parser=url_parser)
        callback_handler = CallbackQueryHandler(media_service=self._media_service)

        auth_middleware = AuthMiddleware(allowed_users=settings.ALLOWED_USERS)
        rate_limit_middleware = RateLimitMiddleware()

        self._application = (
            ApplicationBuilder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .concurrent_updates(settings.WORKER_CONCURRENCY)
            .post_init(self._post_init)
            .post_shutdown(self._post_shutdown)
            .build()
        )

        for group in self._application.handler_groups.values():
            for handler in group.handlers:
                original_callback = handler.callback
                handler.callback = self._wrap_with_middlewares(
                    original_callback, auth_middleware, rate_limit_middleware
                )

        message_handler.register(self._application)
        callback_handler.register(self._application)

        logger.info("bot_initialized")

    async def _post_init(self, application: Any) -> None:
        """Post-initialization hook."""
        logger.info("bot_started_polling")

    async def _post_shutdown(self, application: Any) -> None:
        """Post-shutdown hook."""
        logger.info("bot_stopped_polling")
        if self._queue:
            await self._queue.shutdown()
        if self._storage:
            self._storage.shutdown()

    async def start(self) -> None:
        """Start the bot."""
        if not self._application:
            raise ConfigurationError("Bot not initialized. Call initialize() first.")

        logger.info("bot_starting")

        def handle_signal() -> None:
            logger.info("shutdown_signal_received")
            self._shutdown_event.set()

        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, handle_signal)

        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling()

        await self._shutdown_event.wait()

        await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown the bot."""
        logger.info("bot_shutting_down")

        if self._application:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()

        logger.info("bot_shutdown_complete")

    def _validate_config(self) -> None:
        """Validate critical configuration."""
        if not settings.TELEGRAM_BOT_TOKEN:
            raise ConfigurationError("TELEGRAM_BOT_TOKEN is not set")

        if not settings.TEMP_STORAGE_PATH.exists():
            settings.TEMP_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

    def _wrap_with_middlewares(self, callback: Any, *middlewares: Any) -> Any:
        """Wrap handler callback with middleware chain."""

        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            for middleware in middlewares:
                await middleware(update, context, callback)
            await callback(update, context)

        return wrapped


def create_bot() -> DownloaderBot:
    """Factory function for creating bot instance."""
    return DownloaderBot()


async def main() -> None:
    """Main entry point."""
    bot = create_bot()
    try:
        await bot.initialize()
        await bot.start()
    except Exception as exc:
        log_error_with_context(exc, context={"phase": "main"})
        logger.error("bot_fatal_error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
