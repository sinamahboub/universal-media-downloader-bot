"""
File lifecycle management for downloaded media.

Handles temporary storage, file naming, cleanup, and
fallback link generation when files exceed Telegram limits.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import settings
from core.exceptions import StorageError
from core.logger import StructuredLogger

logger = StructuredLogger(component="storage")


@dataclass
class FileInfo:
    """Metadata about a stored file."""

    job_id: str
    file_path: Path
    file_name: str
    file_size: int
    mime_type: str
    extension: str
    created_at: datetime
    user_id: int
    url: str

    def exceeds_telegram_limit(self) -> bool:
        """Check if file exceeds Telegram's upload limit."""
        return self.file_size > (settings.MAX_FILE_SIZE_MB * 1024 * 1024)


class StorageManager:
    """
    Manages temporary file storage lifecycle.

    Responsibilities:
    - Create unique, safe file paths
    - Track metadata for all stored files
    - Clean up temporary files after delivery
    - Handle disk space management
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self.base_path = base_path or settings.TEMP_STORAGE_PATH
        self._file_registry: dict[str, FileInfo] = {}
        self._cleanup_interval = 3600  # 1 hour
        self._max_age_seconds = 86400  # 24 hours

        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("storage_initialized", base_path=str(self.base_path))

    def _generate_safe_filename(self, job_id: str, extension: str) -> str:
        """
        Generate a safe, unique filename.

        Args:
            job_id: Download job identifier
            extension: File extension with dot

        Returns:
            Safe filename string
        """
        timestamp = int(time.time())
        return f"{job_id}_{timestamp}{extension}"

    def get_storage_path(self, job_id: str, extension: str) -> Path:
        """
        Generate a storage path for a new file.

        Args:
            job_id: Download job identifier
            extension: File extension with dot

        Returns:
            Full path where file should be stored
        """
        filename = self._generate_safe_filename(job_id, extension)
        return self.base_path / filename

    def register_file(
        self,
        job_id: str,
        file_path: Path,
        file_size: int,
        mime_type: str,
        user_id: int,
        url: str,
    ) -> FileInfo:
        """
        Register a downloaded file in the storage system.

        Args:
            job_id: Download job identifier
            file_path: Path to the downloaded file
            file_size: File size in bytes
            mime_type: MIME type of the file
            user_id: Telegram user ID
            url: Source URL

        Returns:
            FileInfo with metadata
        """
        extension = file_path.suffix.lower()
        file_info = FileInfo(
            job_id=job_id,
            file_path=file_path,
            file_name=file_path.name,
            file_size=file_size,
            mime_type=mime_type,
            extension=extension,
            created_at=datetime.utcnow(),
            user_id=user_id,
            url=url,
        )

        self._file_registry[job_id] = file_info
        logger.info(
            "file_registered",
            job_id=job_id,
            path=str(file_path),
            size_bytes=file_size,
            mime_type=mime_type,
        )

        return file_info

    def get_file_info(self, job_id: str) -> Optional[FileInfo]:
        """Get stored file metadata by job ID."""
        return self._file_registry.get(job_id)

    def cleanup_file(self, job_id: str) -> bool:
        """
        Delete a file and remove from registry.

        Args:
            job_id: Job identifier whose file should be cleaned up

        Returns:
            True if cleanup was successful
        """
        file_info = self._file_registry.pop(job_id, None)
        if not file_info:
            return False

        try:
            if file_info.file_path.exists():
                file_info.file_path.unlink()
                logger.info(
                    "file_cleaned_up",
                    job_id=job_id,
                    path=str(file_info.file_path),
                )
            return True
        except OSError as exc:
            logger.error(
                "file_cleanup_failed",
                job_id=job_id,
                path=str(file_info.file_path),
                error=str(exc),
            )
            raise StorageError(
                f"Failed to cleanup file: {exc}",
                path=str(file_info.file_path),
            ) from exc

    def cleanup_user_files(self, user_id: int) -> int:
        """
        Clean up all files for a specific user.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of files cleaned up
        """
        cleaned = 0
        jobs_to_remove = [
            job_id for job_id, info in self._file_registry.items() if info.user_id == user_id
        ]

        for job_id in jobs_to_remove:
            if self.cleanup_file(job_id):
                cleaned += 1

        if cleaned:
            logger.info("user_files_cleaned", user_id=user_id, count=cleaned)

        return cleaned

    def cleanup_old_files(self) -> int:
        """
        Remove files older than max age.

        Returns:
            Number of files removed
        """
        cutoff = datetime.utcnow().timestamp() - self._max_age_seconds
        removed = 0

        for job_id, info in list(self._file_registry.items()):
            if info.created_at.timestamp() < cutoff:
                try:
                    self.cleanup_file(job_id)
                    removed += 1
                except StorageError:
                    continue

        if removed:
            logger.info("old_files_cleaned", count=removed, max_age_hours=self._max_age_seconds / 3600)

        return removed

    def get_storage_stats(self) -> dict[str, any]:
        """Get storage usage statistics."""
        total_size = sum(info.file_size for info in self._file_registry.values())
        return {
            "total_files": len(self._file_registry),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "base_path": str(self.base_path),
        }

    def shutdown(self) -> None:
        """Cleanup all registered files on shutdown."""
        logger.info("storage_shutdown_started", file_count=len(self._file_registry))

        for job_id in list(self._file_registry.keys()):
            try:
                self.cleanup_file(job_id)
            except StorageError:
                continue

        logger.info("storage_shutdown_completed")
