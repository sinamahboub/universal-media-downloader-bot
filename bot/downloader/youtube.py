"""YouTube platform downloader implementation."""

import asyncio
from pathlib import Path

import yt_dlp

from .base import BaseDownloader, MediaInfo
from core.config import settings
from core.exceptions import MediaExtractionError, DownloadFailedError
from core.logger import StructuredLogger

logger = StructuredLogger(component="downloader.youtube")


class YouTubeDownloader(BaseDownloader):
    def __init__(self, ffmpeg_available: bool = True) -> None:
        super().__init__(ffmpeg_available)
        self.platform_name = "youtube"

    async def extract_info(self, url: str) -> MediaInfo:
        last_exc = None
        for attempt in self._iter_extraction_attempts(url):
            try:
                info = await self._run_extract(url, attempt)
                return self._build_media_info(url, info)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "youtube_extraction_attempt_failed",
                    url=url,
                    attempt=attempt["layer"],
                    error=str(exc),
                )

        raise MediaExtractionError(
            "YouTube extraction failed after all fallback attempts.",
            url=url,
        ) from last_exc

    async def download(self, url: str, output_path: Path, format_type: str = "audio", quality: str = "best") -> Path:
        output_path.mkdir(parents=True, exist_ok=True)
        ydl_opts = self._build_ydl_opts(output_path, format_type, quality)

        last_exc = None
        for attempt in self._iter_download_attempts(ydl_opts):
            try:
                return await self._run_download(url, output_path, attempt)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "youtube_download_attempt_failed",
                    url=url,
                    attempt=attempt["layer"],
                    error=str(exc),
                )

        raise DownloadFailedError(
            "YouTube download failed after all fallback attempts.",
            details={"url": url},
        ) from last_exc


    def _iter_extraction_attempts(self, url: str):
        attempts = []
        base = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "geo_bypass": True,
            "geo_bypass_country": "US",
            "nocheckcertificate": True,
        }

        attempts.append({
            "layer": "android_no_cookies",
            "ydl_opts": {
                **base,
                "referer": "https://www.youtube.com/",
                "user_agent": (
                    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230901.001) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.130 Mobile Safari/537.36"
                ),
                "extractor_args": {"youtube": {"player_client": ["android"]}},
            },
        })

        if settings.YTDLP_COOKIES_PATH:
            attempts.append({
                "layer": "android_with_cookies",
                "ydl_opts": {
                    **base,
                    "referer": "https://www.youtube.com/",
                    "user_agent": (
                        "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230901.001) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.130 Mobile Safari/537.36"
                    ),
                    "extractor_args": {"youtube": {"player_client": ["android"]}},
                    "cookiefile": str(settings.YTDLP_COOKIES_PATH),
                },
            })

        if settings.YTDLP_PROXY:
            cookie_path = str(settings.YTDLP_COOKIES_PATH) if settings.YTDLP_COOKIES_PATH else None
            attempts.append({
                "layer": "android_with_cookies_and_proxy",
                "ydl_opts": {
                    **base,
                    "referer": "https://www.youtube.com/",
                    "user_agent": (
                        "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230901.001) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.130 Mobile Safari/537.36"
                    ),
                    "extractor_args": {"youtube": {"player_client": ["android"]}},
                    "proxy": str(settings.YTDLP_PROXY),
                    "cookiefile": cookie_path,
                },
            })

        return attempts

    def _iter_download_attempts(self, base_opts):
        attempts = []
        attempts.append({"layer": "base_no_cookies", "ydl_opts": dict(base_opts)})

        if settings.YTDLP_COOKIES_PATH:
            opts = dict(base_opts)
            opts["cookiefile"] = str(settings.YTDLP_COOKIES_PATH)
            attempts.append({"layer": "base_with_cookies", "ydl_opts": opts})

        if settings.YTDLP_PROXY:
            opts = dict(base_opts)
            opts["proxy"] = str(settings.YTDLP_PROXY)
            if settings.YTDLP_COOKIES_PATH:
                opts["cookiefile"] = str(settings.YTDLP_COOKIES_PATH)
            attempts.append({"layer": "base_with_cookies_and_proxy", "ydl_opts": opts})

        return attempts
    async def _run_extract(self, url: str, attempt: dict) -> dict:
        def _extract():
            with yt_dlp.YoutubeDL(attempt["ydl_opts"]) as ydl:
                return ydl.extract_info(url, download=False)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _extract)

    async def _run_download(self, url: str, output_path: Path, attempt: dict) -> Path:
        def _download():
            with yt_dlp.YoutubeDL(attempt["ydl_opts"]) as ydl:
                info = ydl.extract_info(url, download=True)
                if "requested_downloads" in info:
                    return Path(info["requested_downloads"][0]["filepath"])
                return Path(ydl.prepare_filename(info))

        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, _download)

        if self.ffmpeg_available and output_path.suffix == ".mp3":
            file_path = Path(file_path).with_suffix(".mp3")
        elif self.ffmpeg_available and output_path.suffix == ".mp4":
            file_path = Path(file_path).with_suffix(".mp4")

        if not file_path.exists():
            base_name = Path(file_path).stem
            for ext in [".mp3", ".mp4", ".m4a", ".webm"]:
                candidate = output_path / f"{base_name}{ext}"
                if candidate.exists():
                    file_path = candidate
                    break

        return file_path

    def _build_media_info(self, url: str, info: dict) -> MediaInfo:
        is_playlist = info.get("_type") == "playlist" or "entries" in info

        if is_playlist:
            entries = list(info.get("entries", []))
            playlist_count = len(entries)
            title = info.get("title", "Unknown Playlist")
        else:
            playlist_count = None
            title = info.get("title", "Unknown")

        return MediaInfo(
            title=title,
            url=url,
            platform=self.platform_name,
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            uploader=info.get("uploader") or info.get("channel"),
            view_count=info.get("view_count"),
            file_size=info.get("filesize") or info.get("filesize_approx"),
            is_playlist=is_playlist,
            playlist_count=playlist_count,
        )

