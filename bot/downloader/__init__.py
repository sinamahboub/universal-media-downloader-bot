"""
Downloader module initialization.

Exports platform-specific downloaders and factory function.
"""

from .base import BaseDownloader, DownloadOptions, MediaMetadata, MediaType, PlatformType
from .instagram import InstagramDownloader
from .soundcloud import SoundCloudDownloader
from .youtube import YouTubeDownloader

__all__ = [
    "BaseDownloader",
    "DownloadOptions",
    "MediaMetadata",
    "MediaType",
    "PlatformType",
    "YouTubeDownloader",
    "SoundCloudDownloader",
    "InstagramDownloader",
]


class DownloaderFactory:
    """
    Factory for creating platform-specific downloaders.

    Provides URL validation and downloader instantiation
    based on platform detection.
    """

    def __init__(self) -> None:
        self._downloaders: dict[PlatformType, BaseDownloader] = {
            PlatformType.YOUTUBE: YouTubeDownloader(),
            PlatformType.SOUNDCLOUD: SoundCloudDownloader(),
            PlatformType.INSTAGRAM: InstagramDownloader(),
        }

    def detect_platform(self, url: str) -> PlatformType | None:
        """
        Detect which platform a URL belongs to.

        Args:
            url: URL to analyze

        Returns:
            PlatformType if detected, None otherwise
        """
        for downloader in self._downloaders.values():
            if downloader.validate_url(url):
                return downloader.platform_type
        return None

    def get_downloader(self, url: str) -> BaseDownloader | None:
        """
        Get appropriate downloader for URL.

        Args:
            url: Media URL

        Returns:
            Downloader instance if platform is supported
        """
        platform = self.detect_platform(url)
        if platform:
            return self._downloaders[platform]
        return None

    def get_supported_platforms(self) -> list[str]:
        """Get list of supported platform names."""
        return [p.value for p in self._downloaders.keys()]
