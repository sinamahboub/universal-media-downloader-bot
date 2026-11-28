"""
Factory for creating platform-specific downloaders.

Provides a centralized way to instantiate the correct downloader
based on the detected platform from a URL.
"""

from bot.downloader.base import BaseDownloader
from bot.downloader.youtube import YouTubeDownloader
from bot.downloader.soundcloud import SoundCloudDownloader
from bot.downloader.instagram import InstagramDownloader
from bot.services.url_parser import Platform
from core.exceptions import PlatformNotSupportedError
from core.logger import StructuredLogger

logger = StructuredLogger(component="downloader.factory")


class DownloaderFactory:
    """Factory for creating platform-specific downloader instances."""

    # Keyed by Platform enum only. The old map mixed platform names,
    # hostnames and a third-party mirror (ddinstagram.com) as keys,
    # so a hostname could silently resolve to the wrong downloader.
    _platform_map = {
        Platform.YOUTUBE: YouTubeDownloader,
        Platform.SOUNDCLOUD: SoundCloudDownloader,
        Platform.INSTAGRAM: InstagramDownloader,
    }

    @classmethod
    def create(cls, platform: Platform | str, ffmpeg_available: bool = True) -> BaseDownloader:
        """
        Create a downloader instance for the given platform.

        Args:
            platform: Platform enum value (or its string value)
            ffmpeg_available: Whether ffmpeg is available

        Returns:
            Platform-specific downloader instance

        Raises:
            PlatformNotSupportedError: If platform is not supported
        """
        if isinstance(platform, str):
            try:
                platform = Platform(platform.lower())
            except ValueError:
                raise PlatformNotSupportedError(
                    f"Platform '{platform}' is not supported",
                    url="",
                    platform=platform,
                ) from None

        downloader_class = cls._platform_map.get(platform)

        if downloader_class is None:
            raise PlatformNotSupportedError(
                f"Platform '{platform}' is not supported",
                url="",
                platform=platform.value if isinstance(platform, Platform) else str(platform),
            )

        return downloader_class(ffmpeg_available=ffmpeg_available)

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """Return list of supported platform identifiers."""
        return [platform.value for platform in cls._platform_map]
