"""
Centralized exception hierarchy for the downloader bot.

All domain-specific exceptions inherit from these base classes,
ensuring consistent error handling across all layers.
"""


class DownloaderError(Exception):
    """Base exception for all downloader-related errors."""

    def __init__(self, message: str, code: str = "DOWNLOADER_ERROR", details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} | details={self.details}"
        return f"[{self.code}] {self.message}"


class URLValidationError(DownloaderError):
    """Raised when URL fails validation or parsing."""

    def __init__(self, message: str, url: str, details: dict | None = None) -> None:
        super().__init__(message, code="URL_VALIDATION_ERROR", details={"url": url, **(details or {})})
        self.url = url


class PlatformNotSupportedError(DownloaderError):
    """Raised when URL platform is not in supported list."""

    def __init__(self, message: str, url: str, platform: str | None = None) -> None:
        details = {"url": url}
        if platform:
            details["platform"] = platform
        super().__init__(message, code="PLATFORM_NOT_SUPPORTED", details=details)
        self.url = url
        self.platform = platform


class MediaExtractionError(DownloaderError):
    """Raised when yt-dlp fails to extract media info."""

    def __init__(self, message: str, url: str, traceback: str | None = None) -> None:
        details = {"url": url}
        if traceback:
            details["traceback"] = traceback
        super().__init__(message, code="MEDIA_EXTRACTION_ERROR", details=details)
        self.url = url
        self.traceback = traceback


class DownloadFailedError(DownloaderError):
    """Raised when download execution fails."""

    def __init__(self, message: str, job_id: str | None = None, details: dict | None = None) -> None:
        details = details or {}
        if job_id:
            details["job_id"] = job_id
        super().__init__(message, code="DOWNLOAD_FAILED", details=details)
        self.job_id = job_id


class FileSizeLimitExceededError(DownloaderError):
    """Raised when downloaded file exceeds size limits."""

    def __init__(self, message: str, file_size: int, limit: int, job_id: str | None = None) -> None:
        details = {"file_size_bytes": file_size, "limit_bytes": limit}
        super().__init__(message, code="FILE_SIZE_LIMIT_EXCEEDED", details=details)
        self.file_size = file_size
        self.limit = limit
        self.job_id = job_id


class StorageError(DownloaderError):
    """Raised when file storage or cleanup operations fail."""

    def __init__(self, message: str, path: str, details: dict | None = None) -> None:
        details = {"path": path, **(details or {})}
        super().__init__(message, code="STORAGE_ERROR", details=details)
        self.path = path


class QueueError(DownloaderError):
    """Raised when async queue operations fail."""

    def __init__(self, message: str, queue_name: str, details: dict | None = None) -> None:
        details = {"queue": queue_name, **(details or {})}
        super().__init__(message, code="QUEUE_ERROR", details=details)
        self.queue_name = queue_name


class RateLimitExceededError(DownloaderError):
    """Raised when user exceeds rate limits."""

    def __init__(self, message: str, user_id: int, retry_after: int | None = None) -> None:
        details = {"user_id": user_id}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", details=details)
        self.user_id = user_id
        self.retry_after = retry_after


class AuthenticationError(DownloaderError):
    """Raised when user authentication fails."""

    def __init__(self, message: str, user_id: int | None = None) -> None:
        details = {}
        if user_id is not None:
            details["user_id"] = user_id
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details)
        self.user_id = user_id


class ConfigurationError(DownloaderError):
    """Raised when environment or configuration is invalid."""

    pass


class TransientError(DownloaderError):
    """Raised for errors that should be retried with backoff."""

    def __init__(self, message: str, retry_count: int = 0, max_retries: int = 3) -> None:
        details = {"retry_count": retry_count, "max_retries": max_retries}
        super().__init__(message, code="TRANSIENT_ERROR", details=details)
        self.retry_count = retry_count
        self.max_retries = max_retries
