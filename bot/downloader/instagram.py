
"""Instagram platform downloader implementation."""

import asyncio
from pathlib import Path

import yt_dlp

from .base import BaseDownloader, MediaInfo
from core.exceptions import MediaExtractionError, DownloadFailedError
from core.logger import StructuredLogger

logger = StructuredLogger(component="downloader.instagram")


class InstagramDownloader(BaseDownloader):
    def __init__(self, ffmpeg_available: bool = True) -> None:
        super().__init__(ffmpeg_available)
        self.platform_name = "instagram"

    async def extract_info(self, url: str) -> MediaInfo:
        def _extract():
            ydl_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _extract)

            is_playlist = info.get("_type") == "playlist" or "entries" in info

            if is_playlist:
                title = info.get("title", "Instagram Post")
            else:
                title = info.get("title") or info.get("description", "Instagram Media")[:100]

            return MediaInfo(
                title=title,
                url=url,
                platform=self.platform_name,
                duration=info.get("duration"),
                thumbnail=info.get("thumbnail"),
                uploader=info.get("uploader"),
                file_size=info.get("filesize") or info.get("filesize_approx"),
                is_playlist=is_playlist,
            )
        except Exception as exc:
            raise MediaExtractionError(f"Failed to extract Instagram info: {exc}", url=url) from exc

    async def download(self, url: str, output_path: Path, format_type: str = "video", quality: str = "best") -> Path:
        output_path.mkdir(parents=True, exist_ok=True)
        ydl_opts = self._build_ydl_opts(output_path, format_type, quality)

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if "requested_downloads" in info:
                    return Path(info["requested_downloads"][0]["filepath"])
                return Path(ydl.prepare_filename(info))

        try:
            loop = asyncio.get_event_loop()
            file_path = await loop.run_in_executor(None, _download)

            if self.ffmpeg_available and format_type == "audio":
                file_path = Path(file_path).with_suffix(".mp3")

            if not file_path.exists():
                base_name = Path(file_path).stem
                for ext in [".mp4", ".mp3", ".m4a"]:
                    candidate = output_path / f"{base_name}{ext}"
                    if candidate.exists():
                        file_path = candidate
                        break

            return file_path
        except Exception as exc:
            raise DownloadFailedError(f"Instagram download failed: {exc}", details={"url": url}) from exc
