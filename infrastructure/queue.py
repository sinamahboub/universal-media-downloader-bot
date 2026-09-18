"""
Async job queue system for managing download requests.

Provides per-user queue isolation, backpressure handling, and
graceful shutdown semantics for production deployments.
"""

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from core.config import settings
from core.exceptions import QueueError
from core.logger import StructuredLogger

logger = StructuredLogger(component="queue")


class JobStatus(str, Enum):
    """Download job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class DownloadJob:
    """Represents a single download job in the queue."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int = 0
    url: str = ""
    platform: str = ""
    format_type: str = "audio"
    quality: str = "best"
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize job state for persistence or logging."""
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "url": self.url,
            "platform": self.platform,
            "format_type": self.format_type,
            "quality": self.quality,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


@dataclass
class QueueStats:
    """Queue statistics for observability."""

    total_jobs: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    user_active_jobs: Dict[int, int] = field(default_factory=dict)


class AsyncDownloadQueue:
    """
    Async job queue with per-user isolation and backpressure control.

    Responsibilities:
    - Accept and track download jobs
    - Enforce per-user concurrency limits
    - Provide status introspection
    - Handle graceful cancellation
    """

    def __init__(self) -> None:
        self._pending: deque[DownloadJob] = deque()
        self._running: Dict[str, DownloadJob] = {}
        self._user_jobs: Dict[int, list[DownloadJob]] = {}
        self._completed: list[DownloadJob] = []
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(settings.WORKER_POOL_SIZE)
        self._active_workers: Dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()
        self._max_size = settings.JOB_QUEUE_MAX_SIZE

    async def enqueue(self, job: DownloadJob) -> DownloadJob:
        """
        Add a job to the queue.

        Args:
            job: DownloadJob to enqueue

        Returns:
            The enqueued job with assigned job_id

        Raises:
            QueueError: If queue is at capacity
        """
        async with self._lock:
            if len(self._pending) >= self._max_size:
                raise QueueError(
                    "Queue is at maximum capacity",
                    queue_name="download",
                    details={"pending_count": len(self._pending), "max_size": self._max_size},
                )

            job.status = JobStatus.PENDING
            self._pending.append(job)
            self._user_jobs.setdefault(job.user_id, []).append(job)

            logger.info(
                "job_enqueued",
                job_id=job.job_id,
                user_id=job.user_id,
                url=job.url,
                platform=job.platform,
                queue_depth=len(self._pending),
            )

        return job

    async def dequeue(self) -> Optional[DownloadJob]:
        """
        Get next pending job for a user that has capacity.

        Returns:
            Next job to process, or None if no eligible jobs
        """
        async with self._lock:
            for i, job in enumerate(self._pending):
                active_count = sum(
                    1 for j in self._running.values() if j.user_id == job.user_id
                )
                if active_count < settings.MAX_CONCURRENT_DOWNLOADS:
                    if job.job_id in self._cancelled:
                        continue
                    self._pending.remove(job)
                    return job
        return None

    async def mark_running(self, job: DownloadJob, task: asyncio.Task) -> None:
        """Mark job as running and register its task."""
        async with self._lock:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            self._running[job.job_id] = job
            self._active_workers[job.job_id] = task

            logger.info(
                "job_running",
                job_id=job.job_id,
                user_id=job.user_id,
                running_count=len(self._running),
            )

    async def mark_completed(self, job: DownloadJob, result: Any = None) -> None:
        """Mark job as completed with result."""
        async with self._lock:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = result
            self._running.pop(job.job_id, None)
            self._active_workers.pop(job.job_id, None)
            self._completed.append(job)

            logger.info(
                "job_completed",
                job_id=job.job_id,
                user_id=job.user_id,
                duration_seconds=(
                    (job.completed_at - job.started_at).total_seconds() if job.started_at else None
                ),
            )

    async def mark_failed(self, job: DownloadJob, error: str) -> None:
        """Mark job as failed with error message."""
        async with self._lock:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error = error
            self._running.pop(job.job_id, None)
            self._active_workers.pop(job.job_id, None)
            self._completed.append(job)

            logger.error(
                "job_failed",
                job_id=job.job_id,
                user_id=job.user_id,
                error=error,
                retry_count=job.retry_count,
            )

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or running job.

        Args:
            job_id: Job identifier to cancel

        Returns:
            True if cancellation was successful
        """
        async with self._lock:
            if job_id in self._cancelled:
                return True

            self._cancelled.add(job_id)

            # Remove from pending queue if present
            for job in list(self._pending):
                if job.job_id == job_id:
                    self._pending.remove(job)
                    job.status = JobStatus.CANCELLED
                    self._completed.append(job)
                    logger.info("job_cancelled_pending", job_id=job_id, user_id=job.user_id)
                    return True

            # Cancel running task if exists
            if job_id in self._active_workers:
                task = self._active_workers[job_id]
                task.cancel()
                job = self._running.get(job_id)
                if job:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.utcnow()
                    self._completed.append(job)
                    logger.info("job_cancelled_running", job_id=job_id, user_id=job.user_id)
                return True

        return False

    def cancel_user_jobs(self, user_id: int) -> list[str]:
        """
        Cancel all pending and running jobs for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            List of cancelled job IDs
        """
        cancelled_ids: list[str] = []

        for job in list(self._pending):
            if job.user_id == user_id and job.job_id not in self._cancelled:
                self._cancelled.add(job.job_id)
                self._pending.remove(job)
                job.status = JobStatus.CANCELLED
                self._completed.append(job)
                cancelled_ids.append(job.job_id)

        for job_id, task in list(self._active_workers.items()):
            job = self._running.get(job_id)
            if job and job.user_id == user_id:
                self._cancelled.add(job_id)
                task.cancel()
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.utcnow()
                self._completed.append(job)
                cancelled_ids.append(job.job_id)

        if cancelled_ids:
            logger.info("user_jobs_cancelled", user_id=user_id, cancelled_count=len(cancelled_ids))

        return cancelled_ids

    def get_stats(self) -> QueueStats:
        """Get current queue statistics."""
        user_active = {}
        for job in self._running.values():
            user_active[job.user_id] = user_active.get(job.user_id, 0) + 1

        return QueueStats(
            total_jobs=len(self._pending) + len(self._running) + len(self._completed),
            pending_jobs=len(self._pending),
            running_jobs=len(self._running),
            completed_jobs=sum(1 for j in self._completed if j.status == JobStatus.COMPLETED),
            failed_jobs=sum(1 for j in self._completed if j.status == JobStatus.FAILED),
            cancelled_jobs=sum(1 for j in self._completed if j.status == JobStatus.CANCELLED),
            user_active_jobs=user_active,
        )

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        """Get job by ID from any queue state."""
        for collection in [self._pending, list(self._running.values()), self._completed]:
            for job in collection:
                if job.job_id == job_id:
                    return job
        return None

    def get_user_jobs(self, user_id: int) -> list[DownloadJob]:
        """Get all jobs for a specific user."""
        return [
            job
            for job in self._completed
            if job.user_id == user_id
        ]

    async def shutdown(self) -> None:
        """Gracefully shutdown the queue, cancelling all running jobs."""
        logger.info("queue_shutdown_started", active_jobs=len(self._active_workers))

        for task in list(self._active_workers.values()):
            task.cancel()

        self._pending.clear()
        self._running.clear()
        self._active_workers.clear()
        self._user_jobs.clear()

        logger.info("queue_shutdown_completed")
