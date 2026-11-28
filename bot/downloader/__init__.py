
"""Downloader module initialization.

Exposes platform-specific download adapters for yt-dlp integration.
"""

from .base import BaseDownloader, Quality
from .factory import DownloaderFactory
from .instagram import InstagramDownloader
from .soundcloud import SoundCloudDownloader
from .youtube import YouTubeDownloader

__all__ = [
    "BaseDownloader",
    "Quality",
    "YouTubeDownloader",
    "SoundCloudDownloader",
    "InstagramDownloader",
    "DownloaderFactory",
]
