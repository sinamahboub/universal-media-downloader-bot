"""
YouTube and YouTube Music downloader implementation.

Handles single tracks, videos, playlists, and YouTube Music albums.
"""

import re
from pathlib import Path
from typing import Any

from .base import BaseDownloader, DownloadOptions, MediaMetadata, MediaType, PlatformType


class YouTubeDownloader(BaseDownloader):
    """
    YouTube downloader supporting:
    - Single videos
    - Audio-only tracks
    - Full playlists
    - YouTube Music albums
    """

    # YouTube URL patterns
    URL_PATTERNS = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*list=[\w-]+",
        r"(?:https?://)?youtu\.be/[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.platform_type = PlatformType.YOUTUBE

    def validate_url(self, url: str) -> bool:
        """Check if URL is a valid YouTube URL."""
        return any(re.match(pattern, url) for pattern in self.URL_PATTERNS)

    async def extract_info(self, url: str, extract_flat: bool = False) -> MediaMetadata:
        """
        Extract media metadata from YouTube URL.

        Args:
            url: YouTube URL
            extract_flat: If True, only extract playlist metadata

        Returns:
            MediaMetadata with extracted information
        """
        ytdlp_opts = self._build_common_ytdlp_opts(download=False)
        ytdlp_opts["extract_flat"] = extract_flat

        if extract_flat:
            ytdlp_opts["playlistend"] = 1000

        info = await self._run_ytdlp_with_retry(url, ytdlp_opts, "extract")

        platform = self._normalize_platform(info)
        media_type = self._normalize_media_type(info)

        metadata = MediaMetadata(
            url=url,
            platform=platform,
            media_type=media_type,
            title=info.get("title", "Unknown"),
            uploader=info.get("uploader", "Unknown"),
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            webpage_url=info.get("webpage_url", url),
            extractor=info.get("extractor"),
            entries=info.get("entries"),
            raw_info=info,
        )

        logger.info(
            "youtube_metadata_extracted",
            url=url,
            title=metadata.title,
            media_type=media_type.value,
            is_playlist=metadata.is_playlist(),
            entry_count=len(metadata.entries) if metadata.entries else 0,
        )

        return metadata

    async def download(self, url: str, options: DownloadOptions) -> Path:
        """
        Download media from YouTube.

        Args:
            url: YouTube URL
            options: Download configuration

        Returns:
            Path to downloaded file or directory (for playlists)
        """
        output_template = str(
            options.output_path / options.filename_template
            if options.output_path
            else options.filename_template
        )

        ytdlp_opts = self._build_common_ytdlp_opts(download=True)
        ytdlp_opts.update({
            "outtmpl": output_template,
            "noplaylist": False,
            "format": self._build_format_selector(options),
            "postprocessors": self._build_postprocessors(options),
        })

        logger.info(
            "youtube_download_started",
            url=url,
            format_type=options.format_type,
            quality=options.quality,
        )

        info = await self._run_ytdlp_with_retry(url, ytdlp_opts, "download")

        if "requested_downloads" in info:
            downloaded = info["requested_downloads"][0]
            file_path = Path(downloaded.get("filepath", ""))
        elif "_filename" in info:
            file_path = Path(info["_filename"])
        else:
            file_path = self._find_recent_download(options.output_path)

        if not file_path.exists():
            raise MediaExtractionError(
                "Downloaded file not found after completion",
                url=url,
            )

        logger.info(
            "youtube_download_completed",
            url=url,
            path=str(file_path),
            size_bytes=file_path.stat().st_size,
        )

        return file_path

    def _build_format_selector(self, options: DownloadOptions) -> str:
        """Build yt-dlp format selector string."""
        if options.format_type == "audio":
            return "bestaudio/best"
        elif options.format_type == "video":
            quality_map = {
                "best": "bestvideo+bestaudio/best",
                "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
                "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
            }
            return quality_map.get(options.quality, "bestvideo+bestaudio/best")
        return "best"

    def _build_postprocessors(self, options: DownloadOptions) -> list[dict[str, Any]]:
        """Build yt-dlp postprocessor list."""
        processors: list[dict[str, Any]] = []

        if options.format_type == "audio":
            processors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })

        if options.embed_metadata:
            processors.append({"key": "FFmpegMetadata"})

        if options.embed_thumbnail and options.format_type == "audio":
            processors.append({"key": "EmbedThumbnail"})
            processors.append({"key": "FFmpegConvertThumbnails"})

        return processors

    def _find_recent_download(self, output_path: Path | None) -> Path:
        """Find most recently modified file in output directory."""
        if not output_path or not output_path.exists():
            raise MediaExtractionError("Cannot locate downloaded file", url="unknown")

        files = sorted(output_path.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        return files[0] if files else Path()
