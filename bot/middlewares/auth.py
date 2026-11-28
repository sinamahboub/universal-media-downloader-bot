"""
Authentication middleware for Telegram bot.

Enforces user whitelist if configured, rejecting unauthorized users.

python-telegram-bot has no aiogram-style middleware chain, so this is
not registered with ``add_handler``: handlers call
:meth:`AuthMiddleware.check` explicitly at the top of every update
handler (see ``bot.main`` and the handler classes). ``__call__`` is
kept as a plain wrapper for the same check, for code that wants to
wrap a handler function directly.
"""

from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from core.exceptions import AuthenticationError
from core.logger import StructuredLogger

logger = StructuredLogger(component="auth_middleware")


class AuthMiddleware:
    """
    Authentication middleware for Telegram handlers.

    Checks user against whitelist if configured.
    """

    def __init__(self, allowed_users: list[int] | None = None) -> None:
        # None means "read from settings at check time", so tests can
        # change the environment without rebuilding the middleware.
        self._allowed_users = allowed_users

    def _effective_allowlist(self) -> list[int] | None:
        if self._allowed_users is not None:
            return self._allowed_users
        return get_settings().ALLOWED_USERS

    def is_allowed(self, update: Update) -> bool:
        """Return True when the update's user may use the bot."""
        user = update.effective_user
        if not user:
            return False
        allowlist = self._effective_allowlist()
        if allowlist is None:
            return True
        return user.id in allowlist

    async def check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Enforce the whitelist for one update.

        Returns True when the update may proceed. Returns False (after
        telling the user) when the user is not allowed or unknown.
        """
        user = update.effective_user
        if not user:
            logger.warning("auth_no_user")
            return False

        if not self.is_allowed(update):
            logger.warning(
                "auth_denied",
                user_id=user.id,
                username=user.username,
            )
            if update.effective_message is not None:
                await update.effective_message.reply_text(
                    "⛔ You are not authorized to use this bot."
                )
            return False

        logger.debug("auth_allowed", user_id=user.id, username=user.username)
        return True

    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]],
    ) -> None:
        """Wrap a handler with the auth check.

        Raises:
            AuthenticationError: If user is not authorized
        """
        if not await self.check(update, context):
            user = update.effective_user
            raise AuthenticationError(
                "User not in whitelist",
                user_id=user.id if user else None,
            )
        await handler(update, context)
