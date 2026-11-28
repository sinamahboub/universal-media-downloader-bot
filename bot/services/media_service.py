"""
Media download service.

Orchestrates the download process including URL parsing, info extraction,
download execution, and file delivery to users.
"""

import asyncio
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.config import get_settings
from core.exceptions import (
    DownloadFailedError,
    FileSizeLimitExceededError,
    MediaExtractionError,
    PlatformNotSupportedError,
    URLValidationError,
)
from core.logger import StructuredLogger, log_download_job_event
from infrastructure.queue import AsyncDownloadQueue, DownloadJob
from infrastructure.storage import StorageManager

from bot.downloader.factory import DownloaderFactory
from bot.services.url_parser import URLParserService, ParsedURL

logger = StructuredLogger(component="media_service")

# A pending job (URL received, format not chosen yet) lives this long.
# Callbacks arriving after that are told the session expired instead
# of silently downloading a stale URL.
PENDING_JOB_TTL_SECONDS = 15 * 60


@dataclass
class PendingJob:
    """A URL a user sent, waiting for format/quality selection."""

    job_id: str
    user_id: int
    url: str
    platform: str
    format_type: str = "audio"
    created_at: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: int = PENDING_JOB_TTL_SECONDS) -> bool:
        return (time.time() - self.created_at) > ttl_seconds


class MediaDownloadService:
    """Service for managing media downloads."""

    def __init__(
        self,
        download_queue: AsyncDownloadQueue,
        storage_manager: StorageManager,
        ffmpeg_available: bool = True,
    ) -> None:
        self._queue = download_queue
        self._storage = storage_manager
        self._ffmpeg_available = ffmpeg_available
        self._url_parser = URLParserService()
        # Pending jobs, keyed by job_id. This replaces the old
        # single-slot context.user_data["pending_url"]: two URLs from
        # the same user (or two users in a group) no longer overwrite
        # each other, and each job carries its owner for the callback
        # ownership check.
        self._pending: dict[str, PendingJob] = {}

    # -- pending jobs (message -> callback handoff) -------------------

    def parse_url(self, url: str) -> ParsedURL:
        """Validate a URL and detect its platform."""
        return self._url_parser.parse(url)

    def register_pending(self, url: str, user_id: int) -> PendingJob:
        """Store a validated URL and return its pending job.

        Raises:
            URLValidationError: If the URL is not supported.
        """
        parsed = self._url_parser.parse(url)
        if not parsed.is_valid or parsed.platform is None:
            raise URLValidationError(
                parsed.error or "Invalid URL", url=url
            )
        self._prune_expired_pending()
        job = PendingJob(
            job_id=str(uuid.uuid4()),
            user_id=user_id,
            url=url,
            platform=parsed.platform.value,
        )
        self._pending[job.job_id] = job
        return job

    def get_pending(self, job_id: str) -> Optional[PendingJob]:
        """Return a pending job, or None when unknown/expired."""
        self._prune_expired_pending()
        return self._pending.get(job_id)

    def get_pending_for_user(self, job_id: str, user_id: int) -> Optional[PendingJob]:
        """Return a pending job only when it belongs to this user."""
        job = self.get_pending(job_id)
        if job is None or job.user_id != user_id:
            return None
        return job

    def set_pending_format(self, job_id: str, format_type: str) -> None:
        job = self._pending.get(job_id)
        if job is not None:
            job.format_type = format_type

    def pop_pending(self, job_id: str, user_id: int) -> Optional[PendingJob]:
        """Take a pending job out of the registry (ownership-checked)."""
        job = self.get_pending_for_user(job_id, user_id)
        if job is not None:
            del self._pending[job_id]
        return job

    def _prune_expired_pending(self) -> None:
        expired = [job_id for job_id, job in self._pending.items() if job.is_expired()]
        for job_id in expired:
            del self._pending[job_id]

    async def cancel_pending(self, job_id: str, user_id: int) -> bool:
        """Cancel a pending or running job owned by this user."""
        job = self.pop_pending(job_id, user_id)
        cancelled = await self._queue.cancel_job(job_id)
        if job is not None:
            self.cleanup_job_files(job_id)
            return True
        return cancelled

    async def cancel_user_jobs(self, user_id: int) -> list[str]:
        """Cancel every pending/running job of one user."""
        cancelled_ids = [
            job_id for job_id, job in self._pending.items() if job.user_id == user_id
        ]
        for job_id in cancelled_ids:
            del self._pending[job_id]
            self.cleanup_job_files(job_id)
        cancelled_ids.extend(self._queue.cancel_user_jobs(user_id))
        return cancelled_ids

    def cleanup_job_files(self, job_id: str) -> None:
        """Remove the job's temp directory (temp/<job_id>/)."""
        job_dir = get_settings().TEMP_STORAGE_PATH / job_id
        shutil.rmtree(job_dir, ignore_errors=True)

    # -- downloads ----------------------------------------------------

    async def process_url(
        self,
        url: str,
        user_id: int,
        format_type: str = "audio",
        quality: str = "best",
        job_id: str | None = None,
    ) -> tuple[Optional[Path], Optional[str]]:
        """Process a media URL for download.

        The job_id comes from the message handler (one id from the
        URL message all the way through to the callback), so the
        download, its temp directory and its file all carry the same
        id. When no job_id is given one is generated.
        """
        job_id = job_id or str(uuid.uuid4())
        settings = get_settings()

        try:
            parsed = self._url_parser.parse(url)
            if not parsed.is_valid:
                return None, parsed.error or "Invalid URL"

            platform = parsed.platform
            platform_id = parsed.platform_id

            log_download_job_event(
                job_id=job_id,
                event="started",
                user_id=user_id,
                url=url,
                platform=platform_id,
            )

            job = DownloadJob(
                job_id=job_id,
                user_id=user_id,
                url=url,
                platform=platform_id,
                format_type=format_type,
                quality=quality,
            )

            await self._queue.enqueue(job)
            await self._queue.mark_running(job, asyncio.current_task())

            try:
                file_path = await self._execute_download(
                    job=job,
                    platform=platform,
                    format_type=format_type,
                    quality=quality,
                )
            except Exception:
                await self._queue.mark_failed(job, "download failed")
                raise

            file_size = file_path.stat().st_size
            max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024

            if file_size > max_size:
                file_path.unlink(missing_ok=True)
                self.cleanup_job_files(job_id)
                await self._queue.mark_failed(job, "file too large")
                raise FileSizeLimitExceededError(
                    f"File too large: {file_size / (1024 * 1024):.1f}MB exceeds {settings.MAX_FILE_SIZE_MB}MB limit",
                    file_size=file_size,
                    limit=max_size,
                    job_id=job_id,
                )

            mime_type = self._get_mime_type(file_path, format_type)
            self._storage.register_file(
                job_id=job_id,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                user_id=user_id,
                url=url,
            )
            await self._queue.mark_completed(job, result=str(file_path))

            log_download_job_event(
                job_id=job_id,
                event="completed",
                user_id=user_id,
                url=url,
                platform=platform_id,
                extra={"file_size": file_size},
            )

            return file_path, None

        except (FileSizeLimitExceededError, PlatformNotSupportedError, URLValidationError):
            raise
        except Exception as exc:
            logger.error("download_process_failed", job_id=job_id, error=str(exc))
            return None, "Download failed. Please try another link."

    async def _execute_download(self, job, platform, format_type: str, quality: str) -> Path:
        """Execute the actual download operation."""
        settings = get_settings()
        downloader = DownloaderFactory.create(
            platform=platform.value,
            ffmpeg_available=self._ffmpeg_available,
        )

        temp_dir = settings.TEMP_STORAGE_PATH / job.job_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            media_info = await asyncio.wait_for(
                downloader.extract_info(job.url),
                timeout=settings.DOWNLOAD_TIMEOUT_SECONDS,
            )
            logger.info("media_info_extracted", job_id=job.job_id, title=media_info.title)

            # Reject before downloading anything: a playlist link, or
            # a file already known to be bigger than the Telegram
            # limit, must never start a multi-hundred-megabyte
            # download that is only checked afterwards.
            if media_info.is_playlist:
                raise DownloadFailedError(
                    "Playlists are not supported. Send a single video or track link.",
                    job_id=job.job_id,
                )
            max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            if media_info.file_size is not None and media_info.file_size > max_size:
                raise FileSizeLimitExceededError(
                    f"File too large: {media_info.file_size / (1024 * 1024):.1f}MB exceeds "
                    f"{settings.MAX_FILE_SIZE_MB}MB limit",
                    file_size=media_info.file_size,
                    limit=max_size,
                    job_id=job.job_id,
                )

            file_path = await asyncio.wait_for(
                downloader.download(
                    url=job.url,
                    output_path=temp_dir,
                    format_type=format_type,
                    quality=quality,
                    job_id=job.job_id,
                ),
                timeout=settings.DOWNLOAD_TIMEOUT_SECONDS,
            )

            if not file_path.exists():
                raise DownloadFailedError("Downloaded file not found", job_id=job.job_id)

            # The file stays inside temp/<job_id>/ (job-prefixed name).
            # It is removed by cleanup_job_files() after delivery, or
            # on failure below. Never move it to the shared temp root:
            # two downloads of the same video used to collide there.
            resolved = file_path.resolve()
            base = settings.TEMP_STORAGE_PATH.resolve()
            if base not in resolved.parents and resolved != base:
                raise DownloadFailedError(
                    "Downloaded file escaped the temp directory",
                    job_id=job.job_id,
                )

            return file_path

        except (MediaExtractionError, DownloadFailedError, FileSizeLimitExceededError):
            self.cleanup_job_files(job.job_id)
            raise
        except TimeoutError as exc:
            self.cleanup_job_files(job.job_id)
            raise DownloadFailedError(
                f"Download timed out after {settings.DOWNLOAD_TIMEOUT_SECONDS}s",
                job_id=job.job_id,
            ) from exc
        except Exception as exc:
            self.cleanup_job_files(job.job_id)
            raise DownloadFailedError(f"Download execution failed: {exc}", job_id=job.job_id) from exc

    def _get_mime_type(self, file_path: Path, format_type: str) -> str:
        """Determine MIME type from file extension."""
        suffix = file_path.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
        }
        return mime_map.get(suffix, "application/octet-stream")
