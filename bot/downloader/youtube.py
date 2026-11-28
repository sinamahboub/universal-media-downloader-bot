"""YouTube platform downloader implementation."""

from pathlib import Path

from core.config import get_settings
from core.exceptions import DownloadFailedError, MediaExtractionError
from core.logger import StructuredLogger

from .base import BaseDownloader, MediaInfo, YtDlpRunner, is_auth_error

logger = StructuredLogger(component="downloader.youtube")

_ANDROID_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230901.001) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.130 Mobile Safari/537.36"
)


class YouTubeDownloader(BaseDownloader):
    def __init__(self, ffmpeg_available: bool = True) -> None:
        super().__init__(ffmpeg_available)
        self.platform_name = "youtube"

    async def extract_info(self, url: str) -> MediaInfo:
        last_exc = None
        attempts = self._iter_extraction_attempts(url)
        for index, attempt in enumerate(attempts):
            try:
                # Transient errors (429/5xx/network) are retried with
                # exponential backoff inside _with_transient_retry;
                # a permanent error fails fast instead of burning
                # through every fallback layer.
                info = await self._with_transient_retry(
                    lambda a=attempt: YtDlpRunner.extract_info(url, a["ydl_opts"])
                )
                return self._build_media_info(url, info)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "youtube_extraction_attempt_failed",
                    url=url,
                    attempt=attempt["layer"],
                    error=str(exc),
                )
                # Only an auth-looking error is worth the next layer
                # (cookies / proxy); anything else fails here.
                if index < len(attempts) - 1 and is_auth_error(exc):
                    continue
                break

        raise MediaExtractionError(
            "YouTube extraction failed after all fallback attempts.",
            url=url,
        ) from last_exc

    async def download(self, url: str, output_path: Path, format_type: str = "audio", quality: str = "best", job_id: str | None = None) -> Path:
        output_path.mkdir(parents=True, exist_ok=True)
        ydl_opts = self._build_ydl_opts(output_path, format_type, quality, job_id=job_id)

        last_exc = None
        attempts = self._iter_download_attempts(ydl_opts)
        for index, attempt in enumerate(attempts):
            try:
                file_path = await self._with_transient_retry(
                    lambda a=attempt: YtDlpRunner.download(url, a["ydl_opts"])
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "youtube_download_attempt_failed",
                    url=url,
                    attempt=attempt["layer"],
                    error=str(exc),
                )
                if index < len(attempts) - 1 and is_auth_error(exc):
                    continue
                break
            else:
                if self.ffmpeg_available and file_path.suffix == ".mp3":
                    file_path = Path(file_path).with_suffix(".mp3")
                elif self.ffmpeg_available and file_path.suffix == ".mp4":
                    file_path = Path(file_path).with_suffix(".mp4")

                return self._resolve_downloaded_file(
                    output_path, file_path, [".mp3", ".mp4", ".m4a", ".webm"]
                )

        raise DownloadFailedError(
            "YouTube download failed after all fallback attempts.",
            details={"url": url},
        ) from last_exc

    def _iter_extraction_attempts(self, url: str):
        settings = get_settings()
        # NOTE: no nocheckcertificate here on purpose. Disabling TLS
        # verification used to be set in this dict; a forged cert on
        # the network path could then feed tampered extraction data.
        base = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "geo_bypass": True,
            "geo_bypass_country": "US",
        }

        attempts = [{
            "layer": "android_no_cookies",
            "ydl_opts": {
                **base,
                "referer": "https://www.youtube.com/",
                "user_agent": _ANDROID_USER_AGENT,
                "extractor_args": {"youtube": {"player_client": ["android"]}},
            },
        }]

        if settings.YTDLP_COOKIES_PATH:
            attempts.append({
                "layer": "android_with_cookies",
                "ydl_opts": {
                    **base,
                    "referer": "https://www.youtube.com/",
                    "user_agent": _ANDROID_USER_AGENT,
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
                    "user_agent": _ANDROID_USER_AGENT,
                    "extractor_args": {"youtube": {"player_client": ["android"]}},
                    "proxy": str(settings.YTDLP_PROXY),
                    "cookiefile": cookie_path,
                },
            })

        return attempts

    def _iter_download_attempts(self, base_opts):
        settings = get_settings()
        attempts = [{"layer": "base_no_cookies", "ydl_opts": dict(base_opts)}]

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

    def _build_media_info(self, url: str, info: dict) -> MediaInfo:
        is_playlist = info.get("_type") == "playlist" or "entries" in info

        if is_playlist:
            entries = list(info.get("entries", []))
            playlist_count = len(entries)
            title = info.get("title") or "Unknown Playlist"
        else:
            playlist_count = None
            title = info.get("title") or "Unknown"

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
