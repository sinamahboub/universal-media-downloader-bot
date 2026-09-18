
"""
Callback query handlers for Telegram bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from core.config import settings
from core.exceptions import DownloadFailedError, FileSizeLimitExceededError, MediaExtractionError
from core.logger import StructuredLogger
from bot.keyboards.inline import quality_keyboard
from bot.services.media_service import MediaDownloadService

logger = StructuredLogger(component="handlers.callback")


class CallbackQueryHandler:
    def __init__(self, media_service: MediaDownloadService) -> None:
        self._media_service = media_service

    async def handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        parts = query.data.split(":")
        if len(parts) != 3 or parts[0] != "fmt":
            await query.edit_message_text("Invalid selection.")
            return
        format_type = parts[1]
        job_id = parts[2]
        context.user_data["format_type"] = format_type

        if format_type == "video":
            await query.edit_message_text(
                "Select quality:",
                reply_markup=quality_keyboard(format_type, job_id),
            )
        else:
            await query.edit_message_text("Starting download...")
            await self._start_download(query, context, format_type, "best")

    async def handle_quality_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        parts = query.data.split(":")
        if len(parts) != 3 or parts[0] != "qual":
            await query.edit_message_text("Invalid selection.")
            return
        quality = parts[1]
        format_type = context.user_data.get("format_type", "video")
        await query.edit_message_text("Starting download...")
        await self._start_download(query, context, format_type, quality)

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Download cancelled.")

    async def _start_download(self, query, context: ContextTypes.DEFAULT_TYPE, format_type: str, quality: str) -> None:
        url = context.user_data.get("pending_url")
        user_id = context.user_data.get("user_id")
        if not url:
            await query.edit_message_text("Session expired. Please send URL again.")
            return
        status_msg = await query.edit_message_text(
            f"Downloading {format_type.upper()} ({quality})..."
        )
        try:
            file_path, error = await self._media_service.process_url(
                url=url, user_id=user_id, format_type=format_type, quality=quality,
            )
            if error or not file_path:
                await status_msg.edit_text(f"Download failed: {error}")
                return
            file_size = file_path.stat().st_size
            max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            if file_size > max_size:
                await status_msg.edit_text(
                    f"File too large ({file_size / (1024 * 1024):.1f}MB). Telegram limit is {settings.MAX_FILE_SIZE_MB}MB."
                )
                file_path.unlink(missing_ok=True)
                return
            await status_msg.edit_text("Uploading to Telegram...")
            with open(file_path, "rb") as media_file:
                if format_type == "audio":
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id, audio=media_file, caption="Downloaded!",
                    )
                else:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id, video=media_file, caption="Downloaded!",
                    )
            await status_msg.delete()
            file_path.unlink(missing_ok=True)
        except FileSizeLimitExceededError as exc:
            await status_msg.edit_text(f"File too large: {exc.file_size / (1024 * 1024):.1f}MB")
        except DownloadFailedError as exc:
            await status_msg.edit_text(f"Download failed: {exc.message}")
        except MediaExtractionError as exc:
            await status_msg.edit_text(
                "YouTube extraction failed. If this is a YouTube link, "
                "try setting YTDLP_COOKIES_PATH or YTDLP_PROXY in .env."
            )
        except Exception as exc:
            logger.error("download_handler_failed", error=str(exc))
            await status_msg.edit_text(f"Error: {str(exc)[:200]}")
