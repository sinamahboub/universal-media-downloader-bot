
"""Base downloader abstraction for all platforms.

Defines the interface contract that all platform-specific downloaders must implement.
"""

import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Awaitable, TypeVar
from dataclasses import dataclass
from datetime import datetime

import yt_dlp

from core.config import get_settings
from core.exceptions import MediaExtractionError, DownloadFailedError
from core.logger import StructuredLogger

logger = StructuredLogger(component="downloader.base")

T = TypeVar("T")

# Substrings that mark an error as transient (worth retrying): rate
# limits, server errors and network failures. Anything else (a
# removed video, a private video, an unsupported URL) is permanent
# and retrying it only burns time and requests.
_TRANSIENT_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "timed out",
    "timeout",
    "connection reset",
    "connection aborted",
    "connection refused",
    "network is unreachable",
    "temporary failure",
    "econnreset",
    "broken pipe",
    "remote end closed",
)

# Errors where another attempt layer (cookies / proxy) might help.
_AUTH_MARKERS = (
    "403",
    "sign in",
    "log in",
    "login required",
    "cookies",
    "age",
    "private",
)


def is_transient_error(exc: BaseException) -> bool:
    """Return True when an error is worth retrying with backoff."""
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def is_auth_error(exc: BaseException) -> bool:
    """Return True when another auth layer might fix the error."""
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _AUTH_MARKERS)


class YtDlpRunner:
    """Shared yt-dlp execution for all platform downloaders.

    yt-dlp is blocking, so every call runs in the default executor
    on the running loop. This replaces the duplicated
    ``asyncio.get_event_loop().run_in_executor`` blocks that each
    downloader used to carry (and ``get_event_loop`` is the wrong
    call inside a coroutine: the running loop is what counts).
    """

    @staticmethod
    async def run(func: Callable[[], T]) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func)

    @staticmethod
    async def extract_info(url: str, ydl_opts: Dict[str, Any]) -> dict:
        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        return await YtDlpRunner.run(_extract)

    @staticmethod
    async def download(url: str, ydl_opts: Dict[str, Any]) -> Path:
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if "requested_downloads" in info:
                    return Path(info["requested_downloads"][0]["filepath"])
                return Path(ydl.prepare_filename(info))

        return await YtDlpRunner.run(_download)


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
            # Never follow a playlist: one URL is one file. Without
            # this a playlist link could download dozens of videos.
            "noplaylist": True,
            "max_downloads": 1,
            # Stop yt-dlp itself from fetching a file bigger than the
            # Telegram limit (the service also checks before and
            # after the download; this is the first line of defence).
            "max_filesize": get_settings().MAX_FILE_SIZE_MB * 1024 * 1024,
            "socket_timeout": 30,
            "retries": get_settings().RETRY_MAX_ATTEMPTS,
            # Titles are user-controlled; restrict the output name to
            # safe characters (with %(id)s as the name, this is a
            # second line of defence against path traversal).
            "restrictfilenames": True,
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

    async def _with_transient_retry(self, func: Callable[[], Awaitable[T]]) -> T:
        """Run a coroutine factory, retrying transient errors only.

        Retries use exponential backoff from the RETRY_* settings.
        A permanent error (removed/private video, bad URL) is raised
        immediately: retrying it cannot help.
        """
        settings = get_settings()
        last_exc: BaseException | None = None
        for attempt in range(settings.RETRY_MAX_ATTEMPTS):
            try:
                return await func()
            except Exception as exc:
                last_exc = exc
                if not is_transient_error(exc) or attempt == settings.RETRY_MAX_ATTEMPTS - 1:
                    raise
                delay = min(
                    settings.RETRY_BASE_DELAY * (2 ** attempt),
                    settings.RETRY_MAX_DELAY,
                )
                logger.warning(
                    "transient_error_retrying",
                    error=str(exc),
                    attempt=attempt + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    def _build_simple_media_info(self, url: str, info: dict, default_title: str) -> MediaInfo:
        """Build MediaInfo from raw yt-dlp info (single-media URLs).

        Shared by the Instagram and SoundCloud downloaders, which
        used to duplicate this block (including the description
        crash: ``info.get('description', default)`` returns None
        when the key exists with a None value, and None[:100]
        raises TypeError).
        """
        is_playlist = info.get("_type") == "playlist" or "entries" in info
        if is_playlist:
            title = info.get("title") or default_title
        else:
            title = (
                info.get("title")
                or (info.get("description") or default_title)[:100]
            )
        return MediaInfo(
            title=title,
            url=url,
            platform=self.platform_name,
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            uploader=info.get("uploader"),
            view_count=info.get("view_count"),
            file_size=info.get("filesize") or info.get("filesize_approx"),
            is_playlist=is_playlist,
            playlist_count=len(list(info.get("entries", []))) if is_playlist else None,
        )

    @staticmethod
    def _resolve_downloaded_file(output_path: Path, file_path: Path, extensions: list[str]) -> Path:
        """Find the real downloaded file when yt-dlp renamed it.

        Post-processing (e.g. audio extraction) changes the
        extension, so the reported path may not exist on disk.
        """
        if file_path.exists():
            return file_path
        base_name = Path(file_path).stem
        for ext in extensions:
            candidate = output_path / f"{base_name}{ext}"
            if candidate.exists():
                return candidate
        return file_path
