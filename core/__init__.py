"""
Core module initialization.

Exposes central configuration, logging, and exception systems.
"""

from .config import settings
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    DownloadFailedError,
    DownloaderError,
    FileSizeLimitExceededError,
    MediaExtractionError,
    PlatformNotSupportedError,
    QueueError,
    RateLimitExceededError,
    StorageError,
    TransientError,
    URLValidationError,
)
from .logger import StructuredLogger, log_download_job_event, log_error_with_context

__all__ = [
    "settings",
    "StructuredLogger",
    "log_download_job_event",
    "log_error_with_context",
    "DownloaderError",
    "URLValidationError",
    "PlatformNotSupportedError",
    "MediaExtractionError",
    "DownloadFailedError",
    "FileSizeLimitExceededError",
    "StorageError",
    "QueueError",
    "RateLimitExceededError",
    "AuthenticationError",
    "ConfigurationError",
    "TransientError",
]
