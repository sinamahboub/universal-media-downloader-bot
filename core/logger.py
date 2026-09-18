"""
Structured logging system for the downloader bot.

Provides JSON-formatted logs with consistent fields for observability
and integration with Sentry-style error tracking.
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def log_download_job_event(
    job_id: str,
    event: str,
    user_id: int,
    url: str,
    platform: str,
    extra: dict | None = None,
) -> None:
    """
    Log a structured download job event for observability.

    Args:
        job_id: Unique job identifier
        event: Event type (e.g., "started", "completed", "failed")
        user_id: Telegram user ID
        url: Source URL
        platform: Detected platform name
        extra: Additional context fields
    """
    log_data = {
        "event_type": "download_job",
        "job_id": job_id,
        "event_name": event,
        "user_id": user_id,
        "url": url,
        "platform": platform,
    }
    if extra:
        log_data.update(extra)

    logger.info("download_job_event", **log_data)


def log_error_with_context(
    error: Exception,
    context: dict | None = None,
    job_id: str | None = None,
) -> None:
    """
    Log an error with full context for debugging.

    Args:
        error: The exception that occurred
        context: Additional context about the failure
        job_id: Optional job ID for correlation
    """
    log_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }
    if context:
        log_data["context"] = context
    if job_id:
        log_data["job_id"] = job_id

    logger.error("application_error", **log_data)


def log_platform_detection(url: str, platform: str, confidence: str = "high") -> None:
    """
    Log platform detection result.

    Args:
        url: The URL that was analyzed
        platform: Detected platform name
        confidence: Detection confidence level
    """
    logger.info(
        "platform_detected",
        event_type="platform_detection",
        url=url,
        platform=platform,
        confidence=confidence,
    )


def log_rate_limit(user_id: int, action: str, limit: int, remaining: int) -> None:
    """
    Log rate limit event.

    Args:
        user_id: User who hit the limit
        action: Action that was rate limited
        limit: Rate limit threshold
        remaining: Remaining requests
    """
    logger.warning(
        "rate_limit",
        event_type="rate_limit",
        user_id=user_id,
        action=action,
        limit=limit,
        remaining=remaining,
    )


class StructuredLogger:
    """
    Wrapper class for consistent logging across the application.

    Provides context-aware logging with automatic field injection.
    """

    def __init__(self, component: str) -> None:
        self.component = component
        self._logger = logger.bind(component=component)

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(message, **kwargs)
