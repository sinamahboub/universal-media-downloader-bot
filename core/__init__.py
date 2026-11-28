"""
Core module initialization.

Exposes central configuration, logging, and exception systems.
"""

from .config import get_settings, reset_settings_cache
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    DownloaderError,
    DownloadFailedError,
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
    "get_settings",
    "reset_settings_cache",
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


def __getattr__(name: str):
    # ``settings`` resolves lazily so importing ``core`` never fails
    # when no bot token is configured (see core.config).
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
