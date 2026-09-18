"""
Inline keyboard builders for Telegram bot UI.

Provides reusable keyboard layouts for format selection,
quality selection, cancellation, and main menu navigation.
"""

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards.layouts import (
    CANCEL_BUTTON,
    DOWNLOAD_AUDIO_BUTTON,
    DOWNLOAD_VIDEO_BUTTON,
    QUALITY_1080P_BUTTON,
    QUALITY_480P_BUTTON,
    QUALITY_720P_BUTTON,
    QUALITY_BEST_BUTTON,
)


def format_keyboard(url: str) -> InlineKeyboardMarkup:
    """
    Build format selection keyboard.

    Args:
        url: URL to download (passed as callback data)

    Returns:
        InlineKeyboardMarkup with audio/video options
    """
    keyboard = [
        [
            InlineKeyboardButton(text=DOWNLOAD_AUDIO_BUTTON, callback_data=f"fmt:audio:{url}"),
            InlineKeyboardButton(text=DOWNLOAD_VIDEO_BUTTON, callback_data=f"fmt:video:{url}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def quality_keyboard(format_type: str, url: str) -> InlineKeyboardMarkup:
    """
    Build quality selection keyboard.

    Args:
        format_type: "audio" or "video"
        url: URL to download

    Returns:
        InlineKeyboardMarkup with quality options
    """
    if format_type == "audio":
        keyboard = [
            [InlineKeyboardButton(text=QUALITY_BEST_BUTTON, callback_data=f"qual:best:{url}")]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(text=QUALITY_BEST_BUTTON, callback_data=f"qual:best:{url}"),
            ],
            [
                InlineKeyboardButton(text=QUALITY_1080P_BUTTON, callback_data=f"qual:1080p:{url}"),
                InlineKeyboardButton(text=QUALITY_720P_BUTTON, callback_data=f"qual:720p:{url}"),
            ],
            [
                InlineKeyboardButton(text=QUALITY_480P_BUTTON, callback_data=f"qual:480p:{url}"),
            ],
        ]

    return InlineKeyboardMarkup(keyboard)


def cancel_keyboard(job_id: str) -> InlineKeyboardMarkup:
    """
    Build cancellation keyboard.

    Args:
        job_id: Job to cancel

    Returns:
        InlineKeyboardMarkup with cancel button
    """
    keyboard = [
        [InlineKeyboardButton(text=CANCEL_BUTTON, callback_data=f"cancel:{job_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Build main menu keyboard.

    Returns:
        InlineKeyboardMarkup with main options
    """
    keyboard = [
        [InlineKeyboardButton(text="📥 Send URL", callback_data="menu:send_url")],
    ]
    return InlineKeyboardMarkup(keyboard)
