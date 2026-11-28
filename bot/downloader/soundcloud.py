
"""SoundCloud platform downloader implementation."""

from pathlib import Path

from core.exceptions import DownloadFailedError, MediaExtractionError

from .base import BaseDownloader, MediaInfo, YtDlpRunner

_BASIC_OPTS = {"quiet": True, "no_warnings": True, "noplaylist": True}


class SoundCloudDownloader(BaseDownloader):
    def __init__(self, ffmpeg_available: bool = True) -> None:
        super().__init__(ffmpeg_available)
        self.platform_name = "soundcloud"

    async def extract_info(self, url: str) -> MediaInfo:
        try:
            info = await self._with_transient_retry(
                lambda: YtDlpRunner.extract_info(url, _BASIC_OPTS)
            )
            return self._build_simple_media_info(url, info, "Unknown")
        except MediaExtractionError:
            raise
        except Exception as exc:
            raise MediaExtractionError(f"Failed to extract SoundCloud info: {exc}", url=url) from exc

    async def download(self, url: str, output_path: Path, format_type: str = "audio", quality: str = "best", job_id: str | None = None) -> Path:
        output_path.mkdir(parents=True, exist_ok=True)
        ydl_opts = self._build_ydl_opts(output_path, format_type, quality, job_id=job_id)

        try:
            file_path = await self._with_transient_retry(
                lambda: YtDlpRunner.download(url, ydl_opts)
            )

            if self.ffmpeg_available and format_type == "audio":
                file_path = Path(file_path).with_suffix(".mp3")

            return self._resolve_downloaded_file(
                output_path, file_path, [".mp3", ".m4a", ".wav", ".ogg"]
            )
        except Exception as exc:
            raise DownloadFailedError(f"SoundCloud download failed: {exc}", details={"url": url}) from exc
