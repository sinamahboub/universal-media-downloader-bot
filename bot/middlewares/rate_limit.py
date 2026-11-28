"""
Rate limiting middleware for Telegram bot.

Implements per-user rate limiting using sliding window algorithm.

python-telegram-bot has no aiogram-style middleware chain, so this is
not registered with ``add_handler``: handlers call
:meth:`RateLimitMiddleware.check` explicitly at the top of every
download entry point. ``__call__`` is kept as a plain wrapper for
the same check.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from core.exceptions import RateLimitExceededError
from core.logger import StructuredLogger, log_rate_limit

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
        settings = get_settings()
        self._max_requests = max_requests if max_requests is not None else settings.RATE_LIMIT_REQUESTS
        self._window_seconds = (
            window_seconds if window_seconds is not None else settings.RATE_LIMIT_WINDOW_SECONDS
        )
        self._user_limits: dict[int, UserRateLimit] = defaultdict(UserRateLimit)
        self._lock = asyncio.Lock()

    async def allow_user(self, user_id: int) -> tuple[bool, int | None]:
        """Check the rate limit for a bare user id.

        Returns ``(True, None)`` when the user may proceed, or
        ``(False, retry_after_seconds)`` when limited. Used by
        callback handlers, which only have a CallbackQuery, not a
        full Update, at download time.
        """
        async with self._lock:
            user_limit = self._user_limits[user_id]

            if self._is_rate_limited(user_limit):
                retry_after = self._calculate_retry_after(user_limit)
                log_rate_limit(
                    user_id,
                    "download_request",
                    self._max_requests,
                    self._get_remaining(user_limit),
                )
                return False, retry_after

            self._record_request(user_limit)

        return True, None

    async def check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, int | None]:
        """Enforce the rate limit for one update.

        Returns ``(True, None)`` when the update may proceed, or
        ``(False, retry_after_seconds)`` when the user is limited
        (after telling the user).
        """
        user = update.effective_user
        if not user:
            return False, None

        allowed, retry_after = await self.allow_user(user.id)
        if not allowed:
            if update.effective_message is not None:
                await update.effective_message.reply_text(
                    f"⚠️ Rate limit exceeded. Try again in {retry_after} seconds."
                )
        return allowed, retry_after

    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]],
    ) -> None:
        """Wrap a handler with the rate limit check.

        Raises:
            RateLimitExceededError: If user exceeds rate limit
        """
        allowed, retry_after = await self.check(update, context)
        if not allowed:
            user = update.effective_user
            raise RateLimitExceededError(
                "Rate limit exceeded.",
                user_id=user.id if user else 0,
                retry_after=retry_after,
            )
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
