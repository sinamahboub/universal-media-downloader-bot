"""
Authentication middleware for Telegram bot.

Enforces user whitelist if configured, rejecting unauthorized users.
"""

import logging
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import ContextTypes

from core.config import settings
from core.exceptions import AuthenticationError
from core.logger import StructuredLogger

logger = StructuredLogger(component="auth_middleware")


class AuthMiddleware:
    """
    Authentication middleware for Telegram handlers.

    Checks user against whitelist if configured.
    """

    def __init__(self, allowed_users: list[int] | None = None) -> None:
        self._allowed_users = allowed_users

    async def __call__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]],
    ) -> None:
        """
        Process update through auth check.

        Args:
            update: Telegram update
            context: Handler context
            handler: Next handler in chain

        Raises:
            AuthenticationError: If user is not authorized
        """
        user = update.effective_user
        if not user:
            logger.warning("auth_no_user")
            return

        if self._allowed_users is not None and user.id not in self._allowed_users:
            logger.warning(
                "auth_denied",
                user_id=user.id,
                username=user.username,
            )
            await update.effective_message.reply_text(
                "⛔ You are not authorized to use this bot."
            )
            raise AuthenticationError("User not in whitelist", user_id=user.id)

        logger.debug("auth_allowed", user_id=user.id, username=user.username)
        await handler(update, context)
