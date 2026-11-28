
"""Downloader module initialization.

Exposes platform-specific download adapters for yt-dlp integration.
"""

from .base import BaseDownloader, Quality
from .youtube import YouTubeDownloader
from .soundcloud import SoundCloudDownloader
from .instagram import InstagramDownloader
from .factory import DownloaderFactory

__all__ = [
    "BaseDownloader",
    "Quality",
    "YouTubeDownloader",
    "SoundCloudDownloader",
    "InstagramDownloader",
    "DownloaderFactory",
]
