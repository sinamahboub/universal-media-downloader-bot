"""
Infrastructure module initialization.

Exposes core infrastructure components for dependency injection.
"""

from .cache import AsyncCache
from .lock import SingleInstanceLock, LockManager, ensure_single_instance
from .queue import AsyncDownloadQueue, DownloadJob, JobStatus, QueueStats
from .storage import FileInfo, StorageManager

__all__ = [
    "AsyncCache",
    "SingleInstanceLock",
    "LockManager",
    "ensure_single_instance",
    "AsyncDownloadQueue",
    "DownloadJob",
    "JobStatus",
    "QueueStats",
    "FileInfo",
    "StorageManager",
]
