"""
Telegram message handlers.

Handles /start, /help, /cancel, and URL input messages.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler as TelegramMessageHandler, filters

from core.logger import StructuredLogger
from bot.keyboards.inline import format_keyboard
from bot.services import URLParserService

logger = StructuredLogger(component="message_handler")


class MessageHandler:
    """
    Handles text messages and commands from users.

    Responsibilities:
    - Start/help commands
    - URL detection and validation
    - Format selection initiation
    - Cancel command
    """

    def __init__(self, url_parser: URLParserService | None = None) -> None:
        self._url_parser = url_parser or URLParserService()

    def register(self, application: Any) -> None:
        """
        Register handlers with telegram application.

        Args:
            application: Telegram Application instance
        """
        application.add_handler(CommandHandler("start", self._start_command))
        application.add_handler(CommandHandler("help", self._help_command))
        application.add_handler(CommandHandler("cancel", self._cancel_command))
        application.add_handler(
            TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        welcome_text = (
            f"👋 Hello {user.first_name}!\n\n"
            "I'm a media downloader bot. Send me a URL from:\n"
            "• YouTube (videos, playlists, YouTube Music)\n"
            "• SoundCloud (tracks, sets)\n"
            "• Instagram (reels, posts)\n\n"
            "I'll download it and send it back to you.\n\n"
            "Use /cancel to stop any active downloads."
        )
        await update.message.reply_text(welcome_text)

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_text = (
            "📖 How to use:\n\n"
            "1. Send me a media URL\n"
            "2. Choose format (Audio/Video)\n"
            "3. Choose quality (if video)\n"
            "4. Wait for download\n\n"
            "Supported platforms:\n"
            "• YouTube\n"
            "• SoundCloud\n"
            "• Instagram\n\n"
            "Commands:\n"
            "/start - Start the bot\n"
            "/help - Show this message\n"
            "/cancel - Cancel active downloads"
        )
        await update.message.reply_text(help_text)

    async def _cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command."""
        user_id = update.effective_user.id
        # This would integrate with the queue system
        await update.message.reply_text(
            "✅ All your active downloads have been cancelled."
        )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle text messages (URL detection).

        Args:
            update: Telegram update
            context: Handler context
        """
        text = update.message.text.strip()
        user_id = update.effective_user.id

        try:
            parsed = self._url_parser.parse(text)
        except Exception as exc:
            await update.message.reply_text(
                f"❌ {exc.message}\n\nPlease send a valid URL from a supported platform."
            )
            return

        # Store URL in context for later retrieval
        # Use a short-lived in-memory store (in production, use Redis/database)
        if not hasattr(context, 'bot_data'):
            context.bot_data = {}
        
        job_id = f"{user_id}_{hash(parsed.normalized_url)}"
        context.bot_data[job_id] = parsed.normalized_url

        await update.message.reply_text(
            f"✅ Platform detected: {parsed.platform.value}\n"
            f"📝 Title: {parsed.original_url}\n\n"
            "Choose format:",
            reply_markup=format_keyboard(job_id),
        )

        logger.info(
            "url_received",
            user_id=user_id,
            url=parsed.normalized_url,
            platform=parsed.platform.value,
        )
