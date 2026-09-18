"""
Base downloader interface and shared utilities.

All platform-specific downloaders inherit from BaseDownloader,
ensuring consistent behavior across YouTube, SoundCloud, and Instagram.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from core.config import settings
from core.exceptions import MediaExtractionError
from core.logger import StructuredLogger

logger = StructuredLogger(component="downloader")


class PlatformType(str, Enum):
    """Supported media platforms."""

    YOUTUBE = "youtube"
    YOUTUBE_MUSIC = "youtube_music"
    SOUNDCLOUD = "soundcloud"
    INSTAGRAM = "instagram"
    UNKNOWN = "unknown"


class MediaType(str, Enum):
    """Types of media content."""

    AUDIO = "audio"
    VIDEO = "video"
    PLAYLIST = "playlist"
    ALBUM = "album"
    UNKNOWN = "unknown"


@dataclass
class MediaMetadata:
    """Extracted media information."""

    url: str
    platform: PlatformType
    media_type: MediaType
    title: str
    uploader: str
    duration: int | None = None
    thumbnail: str | None = None
    webpage_url: str | None = None
    extractor: str | None = None
    entries: list[dict[str, Any]] | None = None
    raw_info: dict[str, Any] | None = None

    def is_playlist(self) -> bool:
        """Check if this is a playlist/album/set."""
        return self.media_type in {MediaType.PLAYLIST, MediaType.ALBUM}


@dataclass
class DownloadOptions:
    """Configuration for a download operation."""

    format_type: str = "audio"  # "audio" or "video"
    quality: str = "best"
    output_path: Path | None = None
    filename_template: str = "%(title)s.%(ext)s"
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    extract_flat: bool = False


class BaseDownloader(ABC):
    """
    Abstract base class for all platform downloaders.

    Provides common functionality and enforces interface consistency
    across different media platforms.
    """

    def __init__(self) -> None:
        self.platform_type: PlatformType = PlatformType.UNKNOWN
        self._ytdlp_options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "no_color": True,
            "geo_bypass": True,
            "socket_timeout": settings.DOWNLOAD_TIMEOUT_SECONDS,
            "retries": settings.RETRY_MAX_ATTEMPTS,
            "fragment_retries": settings.RETRY_MAX_ATTEMPTS,
            "skip_unavailable_fragments": True,
            "keepvideo": False,
            "overwrites": True,
            "concurrent_fragment_downloads": 4,
        }

        if settings.YTDLP_COOKIES_PATH and settings.YTDLP_COOKIES_PATH.exists():
            self._ytdlp_options["cookiefile"] = str(settings.YTDLP_COOKIES_PATH)

        if settings.YTDLP_PROXY:
            self._ytdlp_options["proxy"] = settings.YTDLP_PROXY

    @abstractmethod
    async def extract_info(self, url: str, extract_flat: bool = False) -> MediaMetadata:
        """
        Extract media metadata without downloading.

        Args:
            url: Media URL
            extract_flat: If True, only extract playlist metadata

        Returns:
            MediaMetadata with extracted information
        """
        pass

    @abstractmethod
    async def download(self, url: str, options: DownloadOptions) -> Path:
        """
        Download media to local filesystem.

        Args:
            url: Media URL
            options: Download configuration

        Returns:
            Path to downloaded file

        Raises:
            MediaExtractionError: If download fails
        """
        pass

    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """
        Check if URL is valid for this platform.

        Args:
            url: URL to validate

        Returns:
            True if URL is supported
        """
        pass

    async def _run_ytdlp_with_retry(
        self,
        url: str,
        ytdlp_options: dict[str, Any],
        operation_name: str = "extract",
    ) -> dict[str, Any]:
        """
        Execute yt-dlp with retry and exponential backoff.

        Args:
            url: Target URL
            ytdlp_options: yt-dlp configuration
            operation_name: Operation identifier for logging

        Returns:
            yt-dlp result dictionary

        Raises:
            MediaExtractionError: If all retries fail
        """
        import yt_dlp

        last_error: Exception | None = None
        max_attempts = settings.RETRY_MAX_ATTEMPTS
        base_delay = settings.RETRY_BASE_DELAY
        max_delay = settings.RETRY_MAX_DELAY

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"ytdlp_{operation_name}_started",
                    url=url,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )

                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: yt_dlp.YoutubeDL(ytdlp_options).extract_info(
                        url, download=False
                    ),
                )

                logger.info(
                    f"ytdlp_{operation_name}_completed",
                    url=url,
                    attempt=attempt,
                    success=True,
                )

                return result

            except yt_dlp.utils.DownloadError as exc:
                error_msg = str(exc)
                last_error = exc

                logger.warning(
                    f"ytdlp_{operation_name}_failed",
                    url=url,
                    attempt=attempt,
                    error=error_msg,
                )

                if attempt == max_attempts:
                    raise MediaExtractionError(
                        f"yt-dlp {operation_name} failed: {error_msg}",
                        url=url,
                        traceback=error_msg,
                    ) from exc

                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                await asyncio.sleep(delay)

            except Exception as exc:
                logger.error(
                    f"ytdlp_{operation_name}_error",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                )
                raise MediaExtractionError(
                    f"Unexpected error during {operation_name}: {exc}",
                    url=url,
                ) from exc

        raise MediaExtractionError(
            f"yt-dlp {operation_name} failed after {max_attempts} attempts",
            url=url,
        ) from last_error

    def _build_common_ytdlp_opts(self, download: bool = False) -> dict[str, Any]:
        """Build common yt-dlp options dictionary."""
        opts = dict(self._ytdlp_options)
        opts["download"] = download
        return opts

    def _normalize_platform(self, info: dict[str, Any]) -> PlatformType:
        """Normalize yt-dlp extractor to platform enum."""
        extractor = info.get("extractor", "").lower()
        extractor_key = info.get("extractor_key", "").lower()

        if "youtube" in extractor or "youtube" in extractor_key:
            return PlatformType.YOUTUBE
        if "soundcloud" in extractor or "soundcloud" in extractor_key:
            return PlatformType.SOUNDCLOUD
        if "instagram" in extractor or "instagram" in extractor_key:
            return PlatformType.INSTAGRAM

        return PlatformType.UNKNOWN

    def _normalize_media_type(self, info: dict[str, Any]) -> MediaType:
        """Determine media type from yt-dlp info."""
        if info.get("_type") == "playlist" or "entries" in info:
            if self.platform_type == PlatformType.SOUNDCLOUD:
                return MediaType.ALBUM
            return MediaType.PLAYLIST

        if info.get("vcodec") and info["vcodec"] != "none":
            return MediaType.VIDEO

        return MediaType.AUDIO

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(platform={self.platform_type.value})"
