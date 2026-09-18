"""
SoundCloud downloader implementation.

Handles tracks, sets, and playlists.
"""

import re
from pathlib import Path
from typing import Any

from .base import BaseDownloader, DownloadOptions, MediaMetadata, MediaType, PlatformType


class SoundCloudDownloader(BaseDownloader):
    """
    SoundCloud downloader supporting:
    - Single tracks
    - Sets/playlists
    - Full artist discographies
    """

    URL_PATTERNS = [
        r"(?:https?://)?(?:www\.)?soundcloud\.com/[\w-]+/[\w-]+",
        r"(?:https?://)?(?:www\.)?soundcloud\.com/[\w-]+/sets/[\w-]+",
        r"(?:https?://)?(?:www\.)?soundcloud\.com/[\w-]+/likes",
        r"(?:https?://)?(?:www\.)?soundcloud\.com/[\w-]+/tracks",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.platform_type = PlatformType.SOUNDCLOUD

    def validate_url(self, url: str) -> bool:
        """Check if URL is a valid SoundCloud URL."""
        return any(re.match(pattern, url) for pattern in self.URL_PATTERNS)

    async def extract_info(self, url: str, extract_flat: bool = False) -> MediaMetadata:
        """
        Extract media metadata from SoundCloud URL.

        Args:
            url: SoundCloud URL
            extract_flat: If True, only extract playlist metadata

        Returns:
            MediaMetadata with extracted information
        """
        ytdlp_opts = self._build_common_ytdlp_opts(download=False)
        ytdlp_opts["extract_flat"] = extract_flat
        ytdlp_opts["playlistend"] = 500 if not extract_flat else 1000

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
            "soundcloud_metadata_extracted",
            url=url,
            title=metadata.title,
            media_type=media_type.value,
            is_playlist=metadata.is_playlist(),
            entry_count=len(metadata.entries) if metadata.entries else 0,
        )

        return metadata

    async def download(self, url: str, options: DownloadOptions) -> Path:
        """
        Download media from SoundCloud.

        Args:
            url: SoundCloud URL
            options: Download configuration

        Returns:
            Path to downloaded file or directory (for sets/playlists)
        """
        output_template = str(
            options.output_path / options.filename_template
            if options.output_path
            else options.filename_template
        )

        ytdlp_opts = self._build_common_ytdlp_opts(download=True)
        ytdlp_opts.update({
            "outtmpl": output_template,
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "FFmpegMetadata"},
            ],
        })

        logger.info("soundcloud_download_started", url=url, format_type=options.format_type)

        info = await self._run_ytdlp_with_retry(url, ytdlp_opts, "download")

        if "requested_downloads" in info:
            file_path = Path(info["requested_downloads"][0].get("filepath", ""))
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
            "soundcloud_download_completed",
            url=url,
            path=str(file_path),
            size_bytes=file_path.stat().st_size,
        )

        return file_path

    def _find_recent_download(self, output_path: Path | None) -> Path:
        """Find most recently modified file in output directory."""
        if not output_path or not output_path.exists():
            raise MediaExtractionError("Cannot locate downloaded file", url="unknown")

        files = sorted(output_path.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        return files[0] if files else Path()
