"""
Media download orchestration service.

Coordinates between queue, downloader, and storage systems
to execute complete download workflows.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from core.config import settings
from core.exceptions import (
    DownloadFailedError,
    MediaExtractionError,
    PlatformNotSupportedError,
)
from core.logger import StructuredLogger, log_download_job_event, log_error_with_context
from infrastructure.queue import AsyncDownloadQueue, DownloadJob, JobStatus
from infrastructure.storage import StorageManager

from bot.downloader import BaseDownloader, DownloadOptions, MediaMetadata
from bot.services.url_parser import URLParserService

logger = StructuredLogger(component="media_service")


class MediaDownloadService:
    """
    Orchestrates media download workflows.

    Responsibilities:
    - Accept download requests
    - Queue jobs for async processing
    - Execute downloads via appropriate platform downloader
    - Manage file lifecycle
    - Handle errors and retries
    """

    def __init__(
        self,
        queue: AsyncDownloadQueue,
        storage: StorageManager,
        url_parser: URLParserService | None = None,
    ) -> None:
        self._queue = queue
        self._storage = storage
        self._url_parser = url_parser or URLParserService()

    async def request_download(
        self,
        user_id: int,
        url: str,
        format_type: str = "audio",
        quality: str = "best",
    ) -> DownloadJob:
        """
        Request a new download.

        Args:
            user_id: Telegram user ID
            url: Media URL
            format_type: "audio" or "video"
            quality: Quality preset

        Returns:
            Enqueued DownloadJob

        Raises:
            URLValidationError: If URL is invalid
            PlatformNotSupportedError: If platform not supported
            QueueError: If queue is full
        """
        parsed = self._url_parser.parse(url)

        job = DownloadJob(
            user_id=user_id,
            url=parsed.normalized_url,
            platform=parsed.platform.value,
            format_type=format_type,
            quality=quality,
        )

        await self._queue.enqueue(job)

        log_download_job_event(
            job_id=job.job_id,
            event="requested",
            user_id=user_id,
            url=parsed.normalized_url,
            platform=parsed.platform.value,
            extra={"format_type": format_type, "quality": quality},
        )

        logger.info(
            "download_requested",
            job_id=job.job_id,
            user_id=user_id,
            url=parsed.normalized_url,
            platform=parsed.platform.value,
        )

        return job

    async def process_download(self, job: DownloadJob) -> tuple[Path, str]:
        """
        Execute a download job.

        Args:
            job: DownloadJob to process

        Returns:
            Tuple of (file_path, mime_type)

        Raises:
            DownloadFailedError: If download fails
        """
        downloader = self._get_downloader_for_job(job)
        if not downloader:
            raise DownloadFailedError(
                "No downloader available for platform",
                job_id=job.job_id,
                details={"platform": job.platform},
            )

        temp_dir = settings.TEMP_STORAGE_PATH / job.job_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            options = DownloadOptions(
                format_type=job.format_type,
                quality=job.quality,
                output_path=temp_dir,
            )

            file_path = await downloader.download(job.url, options)

            mime_type = self._guess_mime_type(file_path)

            file_info = self._storage.register_file(
                job_id=job.job_id,
                file_path=file_path,
                file_size=file_path.stat().st_size,
                mime_type=mime_type,
                user_id=job.user_id,
                url=job.url,
            )

            log_download_job_event(
                job_id=job.job_id,
                event="completed",
                user_id=job.user_id,
                url=job.url,
                platform=job.platform,
                extra={"file_path": str(file_path), "size": file_info.file_size},
            )

            return file_path, mime_type

        except Exception as exc:
            log_error_with_context(
                exc,
                context={"job_id": job.job_id, "url": job.url},
                job_id=job.job_id,
            )
            raise

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def cancel_user_downloads(self, user_id: int) -> list[str]:
        """
        Cancel all downloads for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            List of cancelled job IDs
        """
        return self._queue.cancel_user_jobs(user_id)

    def _get_downloader_for_job(self, job: DownloadJob) -> BaseDownloader | None:
        """Get appropriate downloader for job's platform."""
        from bot.downloader import DownloaderFactory

        factory = DownloaderFactory()
        return factory.get_downloader(job.url)

    def _guess_mime_type(self, file_path: Path) -> str:
        """Guess MIME type from file extension."""
        ext = file_path.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".flac": "audio/flac",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
            ".avi": "video/x-msvideo",
        }
        return mime_map.get(ext, "application/octet-stream")
