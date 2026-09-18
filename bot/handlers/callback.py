"""
Telegram callback query handlers.

Handles inline keyboard interactions for format selection,
quality selection, and download cancellation.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from core.config import settings
from core.logger import StructuredLogger, log_error_with_context
from bot.keyboards.inline import cancel_keyboard, quality_keyboard
from bot.services import MediaDownloadService

logger = StructuredLogger(component="callback_handler")


class CallbackQueryHandler:
    """
    Handles callback queries from inline keyboards.

    Responsibilities:
    - Format selection (audio/video)
    - Quality selection
    - Download cancellation
    - Progress updates
    """

    def __init__(self, media_service: MediaDownloadService | None = None) -> None:
        self._media_service = media_service or MediaDownloadService()

    def register(self, application: Any) -> None:
        """
        Register handlers with telegram application.

        Args:
            application: Telegram Application instance
        """
        application.add_handler(
            CallbackQueryHandler(self._handle_format_selection, pattern=r"^fmt:")
        )
        application.add_handler(
            CallbackQueryHandler(self._handle_quality_selection, pattern=r"^qual:")
        )
        application.add_handler(
            CallbackQueryHandler(self._handle_cancel, pattern=r"^cancel:")
        )

    async def _handle_format_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle format selection (audio/video).

        Args:
            update: Telegram update
            context: Handler context
        """
        query = update.callback_query
        await query.answer()

        _, format_type, url = query.data.split(":", 2)

        if format_type == "audio":
            await query.edit_message_text(
                "🎵 Audio selected!\nStarting download...",
            )
        else:
            await query.edit_message_text(
                "🎬 Video selected!\nChoose quality:",
                reply_markup=quality_keyboard(format_type, url),
            )

        logger.info("format_selected", user_id=query.from_user.id, format=format_type)

    async def _handle_quality_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle quality selection for video downloads.

        Args:
            update: Telegram update
            context: Handler context
        """
        query = update.callback_query
        await query.answer()

        _, quality, url = query.data.split(":", 2)

        await query.edit_message_text(
            f"⬇️ Downloading {quality.upper()} video...\nPlease wait."
        )

        logger.info("quality_selected", user_id=query.from_user.id, quality=quality)

    async def _handle_cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle download cancellation.

        Args:
            update: Telegram update
            context: Handler context
        """
        query = update.callback_query
        await query.answer()

        _, job_id = query.data.split(":", 1)

        cancelled = await self._media_service.cancel_user_downloads(query.from_user.id)

        if cancelled:
            await query.edit_message_text("✅ Download cancelled.")
        else:
            await query.edit_message_text("❌ No active downloads to cancel.")

        logger.info("download_cancelled", user_id=query.from_user.id, job_id=job_id)
