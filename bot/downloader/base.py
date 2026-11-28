
"""Base downloader abstraction for all platforms.

Defines the interface contract that all platform-specific downloaders must implement.
"""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from core.exceptions import MediaExtractionError, DownloadFailedError


class Quality(str, Enum):
    """Video quality options, used identically by keyboards, the
    callback handlers and the downloaders.

    The callback data carries ``best``/``1080p``/``720p``/``480p``;
    older code used bare ``1080``/``720``/``480`` in the format-spec
    map, so :meth:`Quality.from_value` accepts both spellings.
    """

    BEST = "best"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"

    @classmethod
    def from_value(cls, value: "Quality | str") -> "Quality":
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().lower()
        aliases = {
            "best": cls.BEST,
            "1080": cls.P1080,
            "1080p": cls.P1080,
            "720": cls.P720,
            "720p": cls.P720,
            "480": cls.P480,
            "480p": cls.P480,
        }
        try:
            return aliases[normalized]
        except KeyError:
            raise ValueError(f"Unknown quality: {value!r}") from None

    @property
    def height(self) -> int | None:
        """Max video height for this quality, or None for best."""
        return {"best": None, "1080p": 1080, "720p": 720, "480p": 480}[self.value]


@dataclass
class MediaInfo:
    """Metadata about downloadable media."""

    title: str
    url: str
    platform: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    view_count: Optional[int] = None
    file_size: Optional[int] = None
    formats: list[Dict[str, Any]] = None
    is_playlist: bool = False
    playlist_count: Optional[int] = None

    def __post_init__(self):
        if self.formats is None:
            self.formats = []


class BaseDownloader(ABC):
    """Abstract base class for all platform downloaders."""

    def __init__(self, ffmpeg_available: bool = True) -> None:
        """
        Initialize the base downloader.

        Args:
            ffmpeg_available: Whether ffmpeg is available for post-processing
        """
        self.ffmpeg_available = ffmpeg_available
        self.platform_name = "unknown"

    @abstractmethod
    async def extract_info(self, url: str) -> MediaInfo:
        """
        Extract media information without downloading.

        Args:
            url: Media URL to extract info from

        Returns:
            MediaInfo with extracted metadata

        Raises:
            MediaExtractionError: If extraction fails
        """
        pass

    @abstractmethod
    async def download(
        self,
        url: str,
        output_path: Path,
        format_type: str = "audio",
        quality: str = "best",
        job_id: str | None = None,
    ) -> Path:
        """
        Download media from URL.

        Args:
            url: Media URL to download
            output_path: Directory where file should be saved
            format_type: "audio" or "video"
            quality: Quality preference ("best", "1080p", "720p", "480p")
            job_id: Download job id; when given, the output file is
                prefixed with it so two users can never collide on
                the same filename

        Returns:
            Path to downloaded file

        Raises:
            DownloadFailedError: If download fails
        """
        pass

    def get_platform_name(self) -> str:
        """Return the platform name this downloader handles."""
        return self.platform_name

    def _build_ydl_opts(
        self,
        output_path: Path,
        format_type: str = "audio",
        quality: str = "best",
        job_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Build yt-dlp options dictionary.

        Args:
            output_path: Output directory path
            format_type: "audio" or "video"
            quality: Quality preference
            job_id: When given, the output filename is prefixed with
                the job id so concurrent downloads never collide

        Returns:
            yt-dlp options dictionary
        """
        filename = "%(id)s.%(ext)s"
        if job_id:
            filename = f"{job_id}_{filename}"
        outtmpl = str(output_path / filename)

        if format_type == "audio":
            format_spec = "bestaudio/best"
            postprocessors = []

            if self.ffmpeg_available:
                postprocessors.append(
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                )
        else:
            # Video format
            format_spec = self._get_video_format_spec(quality)
            postprocessors = []

            if self.ffmpeg_available:
                postprocessors.append(
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferredformat": "mp4",
                    }
                )

        opts = {
            "outtmpl": outtmpl,
            "format": format_spec,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        if postprocessors:
            opts["postprocessors"] = postprocessors

        return opts

    def _get_video_format_spec(self, quality: str) -> str:
        """
        Get yt-dlp format specification for video quality.

        Args:
            quality: Quality string ("best", "1080p", "720p", "480p";
                bare "1080"/"720"/"480" are accepted too)

        Returns:
            yt-dlp format specification string
        """
        if not self.ffmpeg_available:
            # Without ffmpeg, avoid merge formats and prefer single-file downloads
            return "best[ext=mp4]/best/bv+ba/b"

        parsed = Quality.from_value(quality)
        quality_map = {
            Quality.BEST: "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            Quality.P1080: "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
            Quality.P720: "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            Quality.P480: "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
        }
        return quality_map[parsed]
