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


def format_keyboard(job_id: str) -> InlineKeyboardMarkup:
    """
    Build format selection keyboard.

    Args:
        job_id: Job identifier (URL stored in job context)

    Returns:
        InlineKeyboardMarkup with audio/video options
    """
    keyboard = [
        [
            InlineKeyboardButton(text=DOWNLOAD_AUDIO_BUTTON, callback_data=f"fmt:audio:{job_id}"),
            InlineKeyboardButton(text=DOWNLOAD_VIDEO_BUTTON, callback_data=f"fmt:video:{job_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def quality_keyboard(format_type: str, job_id: str) -> InlineKeyboardMarkup:
    """
    Build quality selection keyboard.

    Args:
        format_type: "audio" or "video"
        job_id: Job identifier

    Returns:
        InlineKeyboardMarkup with quality options
    """
    if format_type == "audio":
        keyboard = [
            [InlineKeyboardButton(text=QUALITY_BEST_BUTTON, callback_data=f"qual:best:{job_id}")]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(text=QUALITY_BEST_BUTTON, callback_data=f"qual:best:{job_id}"),
            ],
            [
                InlineKeyboardButton(text=QUALITY_1080P_BUTTON, callback_data=f"qual:1080p:{job_id}"),
                InlineKeyboardButton(text=QUALITY_720P_BUTTON, callback_data=f"qual:720p:{job_id}"),
            ],
            [
                InlineKeyboardButton(text=QUALITY_480P_BUTTON, callback_data=f"qual:480p:{job_id}"),
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
