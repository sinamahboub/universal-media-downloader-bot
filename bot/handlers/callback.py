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

    async def _start_download(
        self,
        query: Any,
        context: ContextTypes.DEFAULT_TYPE,
        url: str,
        user_id: int,
        format_type: str,
        quality: str,
    ) -> None:
        """
        Start download and send file to user.

        Args:
            query: Callback query
            context: Handler context
            url: Media URL
            user_id: Telegram user ID
            format_type: "audio" or "video"
            quality: Quality preset
        """
        try:
            # Request download
            job = await self._media_service.request_download(
                user_id=user_id,
                url=url,
                format_type=format_type,
                quality=quality,
            )
            
            await query.edit_message_text(
                f"⏳ Downloading...\nJob ID: {job.job_id[:8]}..."
            )
            
            # Process download
            file_path, mime_type = await self._media_service.process_download(job)
            
            # Send file to user
            if format_type == "audio":
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=open(file_path, 'rb'),
                    caption=f"✅ Downloaded: {file_path.name}",
                )
            else:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=open(file_path, 'rb'),
                    caption=f"✅ Downloaded: {file_path.name}",
                )
            
            await query.edit_message_text("✅ Download complete!")
            
            logger.info(
                "download_sent_to_user",
                user_id=user_id,
                job_id=job.job_id,
                file_path=str(file_path),
            )
            
        except Exception as exc:
            logger.error(
                "download_failed",
                user_id=user_id,
                url=url,
                error=str(exc),
            )
            await query.edit_message_text(
                f"❌ Download failed: {str(exc)}\nPlease try again later."
            )

    def register(self, application: Any) -> None:
        """
        Register handlers with telegram application.

        Args:
            application: Telegram Application instance
        """
        # In v22, create handler with callback as first positional argument
        from telegram.ext import CallbackQueryHandler as CQH
        
        # Create handler instances properly for v22
        handler = CQH(self._route_callback)
        application.add_handler(handler)

    async def _route_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Route callback to appropriate handler based on data prefix."""
        query = update.callback_query
        data = query.data or ""
        
        if data.startswith("fmt:"):
            await self._handle_format_selection(update, context)
        elif data.startswith("qual:"):
            await self._handle_quality_selection(update, context)
        elif data.startswith("cancel:"):
            await self._handle_cancel(update, context)
        else:
            await query.answer("Unknown action")

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

        _, format_type, job_id = query.data.split(":", 2)
        
        # Retrieve URL from context
        url = context.bot_data.get(job_id) if hasattr(context, 'bot_data') else None
        if not url:
            await query.edit_message_text("❌ Session expired. Please send the URL again.")
            return

        if format_type == "audio":
            await query.edit_message_text(
                "🎵 Audio selected!\nStarting download...",
            )
            # Start download immediately for audio
            await self._start_download(
                query=query,
                context=context,
                url=url,
                user_id=query.from_user.id,
                format_type="audio",
                quality="best"
            )
        else:
            await query.edit_message_text(
                "🎬 Video selected!\nChoose quality:",
                reply_markup=quality_keyboard(format_type, job_id),
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

        _, quality, job_id = query.data.split(":", 2)
        
        # Retrieve URL from context
        url = context.bot_data.get(job_id) if hasattr(context, 'bot_data') else None
        if not url:
            await query.edit_message_text("❌ Session expired. Please send the URL again.")
            return

        await query.edit_message_text(
            f"⬇️ Downloading {quality.upper()} video...\nPlease wait."
        )
        
        # Start download for video
        await self._start_download(
            query=query,
            context=context,
            url=url,
            user_id=query.from_user.id,
            format_type="video",
            quality=quality
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
