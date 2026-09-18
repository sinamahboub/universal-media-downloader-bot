"""
Factory for creating platform-specific downloaders.

Provides a centralized way to instantiate the correct downloader
based on the detected platform from a URL.
"""

from typing import Optional

from .base import BaseDownloader
from .youtube import YouTubeDownloader
from .soundcloud import SoundCloudDownloader
from .instagram import InstagramDownloader
from core.exceptions import PlatformNotSupportedError
from core.logger import StructuredLogger

logger = StructuredLogger(component="downloader.factory")


class DownloaderFactory:
    """Factory for creating platform-specific downloader instances."""

    _platform_map = {
        "youtube": YouTubeDownloader,
        "youtu.be": YouTubeDownloader,
        "youtube.com": YouTubeDownloader,
        "m.youtube.com": YouTubeDownloader,
        "music.youtube.com": YouTubeDownloader,
        "soundcloud": SoundCloudDownloader,
        "on.soundcloud.com": SoundCloudDownloader,
        "instagram": InstagramDownloader,
        "www.instagram.com": InstagramDownloader,
        "ddinstagram.com": InstagramDownloader,
    }

    @classmethod
    def create(cls, platform: str, ffmpeg_available: bool = True) -> BaseDownloader:
        """
        Create a downloader instance for the given platform.

        Args:
            platform: Platform identifier string
            ffmpeg_available: Whether ffmpeg is available

        Returns:
            Platform-specific downloader instance

        Raises:
            PlatformNotSupportedError: If platform is not supported
        """
        downloader_class = cls._platform_map.get(platform.lower())

        if downloader_class is None:
            raise PlatformNotSupportedError(
                f"Platform '{platform}' is not supported",
                url="",
                platform=platform,
            )

        return downloader_class(ffmpeg_available=ffmpeg_available)

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """Return list of supported platform identifiers."""
        return list(set(cls._platform_map.keys()))
