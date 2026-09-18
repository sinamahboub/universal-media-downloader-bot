"""
Media download service.

Orchestrates the download process including URL parsing, info extraction,
download execution, and file delivery to users.
"""

import uuid
from pathlib import Path
from typing import Optional

from core.config import settings
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
from bot.services.url_parser import URLParserService

logger = StructuredLogger(component="media_service")


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

    async def process_url(
        self,
        url: str,
        user_id: int,
        format_type: str = "audio",
        quality: str = "best",
    ) -> tuple[Optional[Path], Optional[str]]:
        """Process a media URL for download."""
        job_id = str(uuid.uuid4())

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

            file_path = await self._execute_download(
                job=job,
                platform=platform,
                format_type=format_type,
                quality=quality,
            )

            file_size = file_path.stat().st_size
            max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024

            if file_size > max_size:
                file_path.unlink(missing_ok=True)
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
            error_msg = f"Download failed: {exc}"
            logger.error("download_process_failed", job_id=job_id, error=str(exc))
            return None, error_msg

    async def _execute_download(self, job, platform, format_type: str, quality: str) -> Path:
        """Execute the actual download operation."""
        downloader = DownloaderFactory.create(
            platform=platform.value,
            ffmpeg_available=self._ffmpeg_available,
        )

        temp_dir = settings.TEMP_STORAGE_PATH / job.job_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            media_info = await downloader.extract_info(job.url)
            logger.info("media_info_extracted", job_id=job.job_id, title=media_info.title)

            file_path = await downloader.download(
                url=job.url,
                output_path=temp_dir,
                format_type=format_type,
                quality=quality,
            )

            if not file_path.exists():
                raise DownloadFailedError("Downloaded file not found", job_id=job.job_id)

            # Move file out of temp job dir before cleanup
            final_path = settings.TEMP_STORAGE_PATH / file_path.name
            if file_path != final_path:
                file_path.replace(final_path)
                file_path = final_path

            return file_path

        except MediaExtractionError:
            raise
        except DownloadFailedError:
            raise
        except Exception as exc:
            raise DownloadFailedError(f"Download execution failed: {exc}", job_id=job.job_id) from exc
        finally:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

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
