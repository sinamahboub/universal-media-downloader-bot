
"""
Callback query handlers for Telegram bot.
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.downloader.base import Quality
from bot.keyboards.inline import quality_keyboard
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.services.media_service import MediaDownloadService, PendingJob
from core.exceptions import DownloadFailedError, FileSizeLimitExceededError, MediaExtractionError
from core.logger import StructuredLogger

logger = StructuredLogger(component="handlers.callback")


class CallbackQueryHandler:
    def __init__(
        self,
        media_service: MediaDownloadService,
        auth: AuthMiddleware | None = None,
        rate_limit: RateLimitMiddleware | None = None,
    ) -> None:
        self._media_service = media_service
        self._auth = auth or AuthMiddleware()
        self._rate_limit = rate_limit or RateLimitMiddleware()

    async def _owned_job(self, query, job_id: str) -> PendingJob | None:
        """Return the pending job only when the tapper owns it.

        An old button, or a button tapped by another user (e.g. in a
        group), must never start a download for someone else's URL.
        """
        job = self._media_service.get_pending_for_user(job_id, query.from_user.id)
        if job is None:
            await query.answer("This button is not for you, or the session expired.")
        return job

    async def handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return
        if not await self._auth.check(update, context):
            await query.answer()
            return
        await query.answer()
        parts = query.data.split(":")
        if len(parts) != 3 or parts[0] != "fmt" or parts[1] not in ("audio", "video"):
            await query.edit_message_text("Invalid selection.")
            return
        format_type = parts[1]
        job_id = parts[2]
        job = await self._owned_job(query, job_id)
        if job is None:
            await query.edit_message_text("Session expired. Please send the URL again.")
            return
        self._media_service.set_pending_format(job_id, format_type)

        if format_type == "video":
            await query.edit_message_text(
                "Select quality:",
                reply_markup=quality_keyboard(format_type, job_id),
            )
        else:
            await query.edit_message_text("Starting download...")
            await self._start_download(query, context, job, format_type, Quality.BEST)

    async def handle_quality_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return
        if not await self._auth.check(update, context):
            await query.answer()
            return
        await query.answer()
        parts = query.data.split(":")
        if len(parts) != 3 or parts[0] != "qual":
            await query.edit_message_text("Invalid selection.")
            return
        try:
            quality = Quality.from_value(parts[1])
        except ValueError:
            await query.edit_message_text("Invalid selection.")
            return
        job_id = parts[2]
        job = await self._owned_job(query, job_id)
        if job is None:
            await query.edit_message_text("Session expired. Please send the URL again.")
            return
        format_type = job.format_type
        await query.edit_message_text("Starting download...")
        await self._start_download(query, context, job, format_type, quality)

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return
        if not await self._auth.check(update, context):
            await query.answer()
            return
        await query.answer()
        parts = query.data.split(":")
        if len(parts) != 2 or parts[0] != "cancel":
            await query.edit_message_text("Invalid selection.")
            return
        job_id = parts[1]
        cancelled = await self._media_service.cancel_pending(job_id, query.from_user.id)
        if cancelled:
            await query.edit_message_text("Download cancelled.")
        else:
            await query.edit_message_text("Nothing to cancel for this download.")

    async def _start_download(self, query, context: ContextTypes.DEFAULT_TYPE, job: PendingJob, format_type: str, quality: Quality) -> None:
        # Take the job out of the registry now: the same button must
        # not start the same download twice.
        self._media_service.pop_pending(job.job_id, job.user_id)

        # Rate limit the download itself (the format/quality taps are
        # navigation; the download is the expensive operation).
        allowed, retry_after = await self._rate_limit.allow_user(query.from_user.id)
        if not allowed:
            await query.edit_message_text(
                f"Rate limit exceeded. Try again in {retry_after} seconds."
            )
            return

        url = job.url
        user_id = job.user_id
        status_msg = await query.edit_message_text(
            f"Downloading {format_type.upper()} ({quality.value})..."
        )
        try:
            file_path, error = await self._media_service.process_url(
                url=url,
                user_id=user_id,
                format_type=format_type,
                quality=quality.value,
                job_id=job.job_id,
            )
            if error or not file_path:
                await status_msg.edit_text("Download failed. Please try another link.")
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
        except FileSizeLimitExceededError as exc:
            await status_msg.edit_text(
                f"File too large ({exc.file_size / (1024 * 1024):.1f}MB). "
                "Try a lower quality or a shorter video."
            )
        except DownloadFailedError:
            await status_msg.edit_text("Download failed. Please try another link.")
        except MediaExtractionError:
            await status_msg.edit_text(
                "Could not read this link. If this is a YouTube link, "
                "try setting YTDLP_COOKIES_PATH or YTDLP_PROXY in .env."
            )
        except Exception as exc:
            logger.error("download_handler_failed", error=str(exc))
            await status_msg.edit_text("An error occurred. Please try again.")
        finally:
            # The file lives in temp/<job_id>/; remove the whole job
            # directory once delivery is done (or failed). The size
            # check lives in the service only -- there is no second
            # size check here anymore.
            self._media_service.cleanup_job_files(job.job_id)
