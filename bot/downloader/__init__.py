
"""Downloader module initialization.

Exposes platform-specific download adapters for yt-dlp integration.
"""

from .base import BaseDownloader
from .youtube import YouTubeDownloader
from .soundcloud import SoundCloudDownloader
from .instagram import InstagramDownloader
from .factory import DownloaderFactory

__all__ = [
    "BaseDownloader",
    "YouTubeDownloader",
    "SoundCloudDownloader",
    "InstagramDownloader",
    "DownloaderFactory",
]
