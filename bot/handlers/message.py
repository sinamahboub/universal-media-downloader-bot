"""
Message handlers for Telegram bot.

Handles incoming text messages containing media URLs and orchestrates
the download workflow.
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards.inline import format_keyboard
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.services.media_service import MediaDownloadService
from core.exceptions import (
    URLValidationError,
)
from core.logger import StructuredLogger

logger = StructuredLogger(component="handlers.message")


class MessageHandler:
    """
    Handles incoming text messages.

    Processes media URLs and initiates download workflow.
    """

    def __init__(
        self,
        media_service: MediaDownloadService,
        auth: AuthMiddleware | None = None,
        rate_limit: RateLimitMiddleware | None = None,
    ) -> None:
        """
        Initialize message handler.

        Args:
            media_service: Media download service instance
            auth: Auth middleware (explicit PTB-native check; PTB has
                no middleware chain, so it is called at the top of
                every handler)
            rate_limit: Rate limit middleware, called the same way
        """
        self._media_service = media_service
        self._auth = auth or AuthMiddleware()
        self._rate_limit = rate_limit or RateLimitMiddleware()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle incoming text messages.

        Args:
            update: Telegram update object
            context: Handler context
        """
        user = update.effective_user
        if user is None or update.message is None or update.message.text is None:
            return

        # Explicit guards: auth first, then rate limit. Both reply to
        # the user themselves when the update is rejected.
        if not await self._auth.check(update, context):
            return
        allowed, _retry_after = await self._rate_limit.check(update, context)
        if not allowed:
            return

        text = update.message.text.strip()
        logger.info("message_received", user_id=user.id, text_length=len(text))

        # Validate the URL before showing any keyboard: an invalid
        # link used to open the format picker anyway, and the error
        # only surfaced after the user had already chosen.
        try:
            pending = self._media_service.register_pending(text, user.id)
        except URLValidationError:
            await update.message.reply_text(
                "❌ Invalid URL. Please send a valid YouTube, SoundCloud, or Instagram link.",
                reply_to_message_id=update.message.message_id,
            )
            return
        except Exception as exc:
            logger.error("message_handling_failed", user_id=user.id, error=str(exc))
            await update.message.reply_text(
                "❌ An error occurred. Please try again.",
                reply_to_message_id=update.message.message_id,
            )
            return

        # One job_id is created here and travels with the job through
        # the format/quality callbacks into the download itself.
        await update.message.reply_text(
            "📥 Select format:",
            reply_markup=format_keyboard(pending.job_id),
            reply_to_message_id=update.message.message_id,
        )

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle /cancel command: cancel the user's pending and running
        downloads for real (the old version only replied "Cancelled").
        """
        user = update.effective_user
        if user is None or update.message is None:
            return
        if not await self._auth.check(update, context):
            return
        cancelled = await self._media_service.cancel_user_jobs(user.id)
        if cancelled:
            await update.message.reply_text(
                f"✅ Cancelled {len(cancelled)} download(s). Send a new URL to download."
            )
        else:
            await update.message.reply_text("✅ Cancelled. Send a new URL to download.")
