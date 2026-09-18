"""
Instagram downloader implementation.

Handles reels, posts, and IGTV videos.
"""

import re
from pathlib import Path
from typing import Any

from .base import BaseDownloader, DownloadOptions, MediaMetadata, MediaType, PlatformType


class InstagramDownloader(BaseDownloader):
    """
    Instagram downloader supporting:
    - Reels
    - Posts
    - Carousels (first item)
    """

    URL_PATTERNS = [
        r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[\w-]+",
        r"(?:https?://)?(?:www\.)?instagram\.com/[\w]+/(?:p|reel)/[\w-]+",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.platform_type = PlatformType.INSTAGRAM

    def validate_url(self, url: str) -> bool:
        """Check if URL is a valid Instagram URL."""
        return any(re.match(pattern, url) for pattern in self.URL_PATTERNS)

    async def extract_info(self, url: str, extract_flat: bool = False) -> MediaMetadata:
        """
        Extract media metadata from Instagram URL.

        Args:
            url: Instagram URL
            extract_flat: Ignored for Instagram (not supported)

        Returns:
            MediaMetadata with extracted information
        """
        ytdlp_opts = self._build_common_ytdlp_opts(download=False)

        info = await self._run_ytdlp_with_retry(url, ytdlp_opts, "extract")

        platform = self._normalize_platform(info)
        media_type = self._normalize_media_type(info)

        metadata = MediaMetadata(
            url=url,
            platform=platform,
            media_type=media_type,
            title=info.get("title", "Instagram Post"),
            uploader=info.get("uploader", "Instagram User"),
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            webpage_url=info.get("webpage_url", url),
            extractor=info.get("extractor"),
            entries=info.get("entries"),
            raw_info=info,
        )

        logger.info(
            "instagram_metadata_extracted",
            url=url,
            title=metadata.title,
            media_type=media_type.value,
            uploader=metadata.uploader,
        )

        return metadata

    async def download(self, url: str, options: DownloadOptions) -> Path:
        """
        Download media from Instagram.

        Args:
            url: Instagram URL
            options: Download configuration

        Returns:
            Path to downloaded file
        """
        output_template = str(
            options.output_path / options.filename_template
            if options.output_path
            else options.filename_template
        )

        ytdlp_opts = self._build_common_ytdlp_opts(download=True)
        ytdlp_opts.update({
            "outtmpl": output_template,
            "format": self._build_format_selector(options),
        })

        logger.info("instagram_download_started", url=url, format_type=options.format_type)

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
            "instagram_download_completed",
            url=url,
            path=str(file_path),
            size_bytes=file_path.stat().st_size,
        )

        return file_path

    def _build_format_selector(self, options: DownloadOptions) -> str:
        """Build yt-dlp format selector for Instagram."""
        if options.format_type == "audio":
            return "bestaudio/best"
        return "bestvideo+bestaudio/best"

    def _find_recent_download(self, output_path: Path | None) -> Path:
        """Find most recently modified file in output directory."""
        if not output_path or not output_path.exists():
            raise MediaExtractionError("Cannot locate downloaded file", url="unknown")

        files = sorted(output_path.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        return files[0] if files else Path()
