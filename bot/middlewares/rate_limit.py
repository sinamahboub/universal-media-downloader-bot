"""
Rate limiting middleware for Telegram bot.

Implements per-user rate limiting using sliding window algorithm.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from core.config import settings
from core.exceptions import RateLimitExceededError
from core.logger import StructuredLogger, log_rate_limit
from telegram import Update
from telegram.ext import ContextTypes

logger = StructuredLogger(component="rate_limit_middleware")


@dataclass
class UserRateLimit:
    """Rate limit state for a single user."""

    requests: list[float] = field(default_factory=list)
    blocked_until: float = 0.0


class RateLimitMiddleware:
    """
    Rate limiting middleware using sliding window.

    Tracks requests per user and blocks when limit is exceeded.
    """

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self._max_requests = max_requests or settings.RATE_LIMIT_REQUESTS
        self._window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        self._user_limits: dict[int, UserRateLimit] = defaultdict(UserRateLimit)
        self._lock = asyncio.Lock()

    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]],
    ) -> None:
        """
        Process update through rate limit check.

        Args:
            update: Telegram update
            context: Handler context
            handler: Next handler in chain

        Raises:
            RateLimitExceededError: If user exceeds rate limit
        """
        user = update.effective_user
        if not user:
            await handler(update, context)
            return

        async with self._lock:
            user_limit = self._user_limits[user.id]

            if self._is_rate_limited(user_limit):
                retry_after = self._calculate_retry_after(user_limit)
                log_rate_limit(
                    user.id,
                    "download_request",
                    self._max_requests,
                    self._get_remaining(user_limit),
                )
                raise RateLimitExceededError(
                    f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    user_id=user.id,
                    retry_after=retry_after,
                )

            self._record_request(user_limit)

        await handler(update, context)

    def _is_rate_limited(self, user_limit: UserRateLimit) -> bool:
        """Check if user is currently rate limited."""
        if time.time() < user_limit.blocked_until:
            return True

        cutoff = time.time() - self._window_seconds
        user_limit.requests = [t for t in user_limit.requests if t > cutoff]

        return len(user_limit.requests) >= self._max_requests

    def _record_request(self, user_limit: UserRateLimit) -> None:
        """Record a new request timestamp."""
        user_limit.requests.append(time.time())

    def _get_remaining(self, user_limit: UserRateLimit) -> int:
        """Get remaining requests for user."""
        return max(0, self._max_requests - len(user_limit.requests))

    def _calculate_retry_after(self, user_limit: UserRateLimit) -> int:
        """Calculate seconds until rate limit resets."""
        if not user_limit.requests:
            return 0
        oldest = min(user_limit.requests)
        reset_time = oldest + self._window_seconds
        return max(1, int(reset_time - time.time()))
