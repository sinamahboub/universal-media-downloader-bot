"""
Message handlers for Telegram bot.

Handles incoming text messages containing media URLs and orchestrates
the download workflow.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from core.config import settings
from core.exceptions import (
    AuthenticationError,
    DownloadFailedError,
    FileSizeLimitExceededError,
    PlatformNotSupportedError,
    RateLimitExceededError,
    URLValidationError,
)
from core.logger import StructuredLogger
from bot.keyboards.inline import format_keyboard
from bot.services.media_service import MediaDownloadService

logger = StructuredLogger(component="handlers.message")


class MessageHandler:
    """
    Handles incoming text messages.

    Processes media URLs and initiates download workflow.
    """

    def __init__(self, media_service: MediaDownloadService) -> None:
        """
        Initialize message handler.

        Args:
            media_service: Media download service instance
        """
        self._media_service = media_service

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle incoming text messages.

        Args:
            update: Telegram update object
            context: Handler context
        """
        user = update.effective_user
        text = update.message.text.strip()

        logger.info("message_received", user_id=user.id, text_length=len(text))

        # Send processing message
        status_msg = await update.message.reply_text(
            "🔍 Processing URL...",
            reply_to_message_id=update.message.message_id,
        )

        try:
            # Store URL in context for callback handler
            context.user_data["pending_url"] = text
            context.user_data["user_id"] = user.id

            # Show format selection keyboard
            import uuid
            job_id = str(uuid.uuid4())
            context.user_data["job_id"] = job_id

            await status_msg.edit_text(
                "📥 Select format:",
                reply_markup=format_keyboard(job_id),
            )

        except RateLimitExceededError as exc:
            await status_msg.edit_text(
                f"⚠️ Rate limit exceeded. Try again in {exc.retry_after} seconds."
            )
        except URLValidationError:
            await status_msg.edit_text(
                "❌ Invalid URL. Please send a valid YouTube, SoundCloud, or Instagram link."
            )
        except PlatformNotSupportedError:
            await status_msg.edit_text(
                "❌ Platform not supported. Please send a YouTube, SoundCloud, or Instagram URL."
            )
        except Exception as exc:
            logger.error("message_handling_failed", user_id=user.id, error=str(exc))
            await status_msg.edit_text(
                f"❌ An error occurred: {str(exc)[:200]}"
            )

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle /cancel command.

        Args:
            update: Telegram update object
            context: Handler context
        """
        await update.message.reply_text("✅ Cancelled. Send a new URL to download.")
