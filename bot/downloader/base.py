
"""Base downloader abstraction for all platforms.

Defines the interface contract that all platform-specific downloaders must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from core.exceptions import MediaExtractionError, DownloadFailedError


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
        quality: str = "best"
    ) -> Path:
        """
        Download media from URL.

        Args:
            url: Media URL to download
            output_path: Directory where file should be saved
            format_type: "audio" or "video"
            quality: Quality preference ("best", "1080", "720", "480")

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
        quality: str = "best"
    ) -> Dict[str, Any]:
        """
        Build yt-dlp options dictionary.

        Args:
            output_path: Output directory path
            format_type: "audio" or "video"
            quality: Quality preference

        Returns:
            yt-dlp options dictionary
        """
        outtmpl = str(output_path / "%(title)s.%(ext)s")

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
                        "preferedformat": "mp4",
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
            quality: Quality string ("best", "1080", "720", "480")

        Returns:
            yt-dlp format specification string
        """
        if not self.ffmpeg_available:
            # Without ffmpeg, avoid merge formats and prefer single-file downloads
            return "best[ext=mp4]/best/bv+ba/b"

        quality_map = {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
            "720": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            "480": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
        }
        return quality_map.get(quality, quality_map["best"])
