"""
URL parsing and platform detection service.

Analyzes URLs to identify the platform and validate download eligibility.

Security: a URL is only accepted when its parsed host is on the
allowlist, its scheme is https, and it carries no userinfo or
non-standard port. The old code only ran a regex over the raw string
(no end anchor, no host parsing), so a crafted URL could pass the
regex while yt-dlp followed a redirect somewhere else entirely.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from core.exceptions import PlatformNotSupportedError, URLValidationError
from core.logger import StructuredLogger

logger = StructuredLogger(component="url_parser")

MAX_URL_LENGTH = 2048

# Hosts we ever fetch from. Anything else (including lookalikes and
# third-party mirrors such as ddinstagram.com) is rejected before
# yt-dlp ever sees the URL.
ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "music.youtube.com",
    "soundcloud.com",
    "on.soundcloud.com",
    "instagram.com",
    "www.instagram.com",
}

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "music.youtube.com"}
_SOUNDCLOUD_HOSTS = {"soundcloud.com", "on.soundcloud.com"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}


class Platform(str, Enum):
    """Supported download platforms."""

    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    INSTAGRAM = "instagram"


@dataclass
class ParsedURL:
    """Result of URL parsing and validation."""

    url: str
    platform: Optional[Platform]
    platform_id: str
    is_valid: bool
    error: Optional[str] = None


class URLParserService:
    """
    Service for parsing and validating media URLs.

    Detects platform from URL patterns and validates URL structure.
    """

    # Path patterns per platform, matched against the parsed path
    # (and query for /watch). A playlist URL is never a valid
    # single-media URL: yt-dlp is run with noplaylist=True.
    _path_patterns = {
        Platform.YOUTUBE: [
            re.compile(r"^/watch$"),  # requires v= in the query
            re.compile(r"^/shorts/[\w-]+/?$"),
            re.compile(r"^/embed/[\w-]+/?$"),
            re.compile(r"^/live/[\w-]+/?$"),
            re.compile(r"^/v/[\w-]+/?$"),
            re.compile(r"^/[\w-]+/?$"),  # youtu.be/<id>
        ],
        Platform.SOUNDCLOUD: [
            re.compile(r"^/[\w-]+/[\w-]+/?$"),
            re.compile(r"^/[\w-]+/sets/[\w-]+/?$"),
            re.compile(r"^/[\w-]+/?$"),  # on.soundcloud.com/<code>
        ],
        Platform.INSTAGRAM: [
            re.compile(r"^/(?:p|reel|reels|tv)/[\w-]+/?$"),
            re.compile(r"^/[\w-]+/(?:p|reel|reels)/[\w-]+/?$"),
        ],
    }

    @classmethod
    def parse(cls, url: str) -> ParsedURL:
        """
        Parse and validate a media URL.

        Args:
            url: URL to parse

        Returns:
            ParsedURL with platform detection results
        """
        url = url.strip()

        if not url:
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="Empty URL provided",
            )

        if len(url) > MAX_URL_LENGTH:
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="URL is too long",
            )

        try:
            parsed = urlparse(url)
        except ValueError:
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="Malformed URL",
            )

        # Scheme, host and authority checks come before any pattern:
        # a regex over the raw string cannot tell a userinfo or a
        # non-standard port from a legitimate host.
        if parsed.scheme.lower() != "https":
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="Only https URLs are supported",
            )

        if parsed.username is not None or parsed.password is not None:
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="URLs with credentials are not allowed",
            )

        try:
            port = parsed.port
        except ValueError:
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="Malformed URL",
            )
        if port is not None and port != 443:
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="URLs with a non-standard port are not allowed",
            )

        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="Unsupported platform. Supported: YouTube, SoundCloud, Instagram",
            )

        # Detect platform from the parsed host, then check the path.
        platform = cls._platform_for_host(host)
        if platform is None or not cls._path_matches(platform, parsed):
            return ParsedURL(
                url=url,
                platform=None,
                platform_id="",
                is_valid=False,
                error="Unsupported platform. Supported: YouTube, SoundCloud, Instagram",
            )

        return ParsedURL(
            url=url,
            platform=platform,
            platform_id=platform.value,
            is_valid=True,
        )

    @classmethod
    def _platform_for_host(cls, host: str) -> Optional[Platform]:
        if host in _YOUTUBE_HOSTS:
            return Platform.YOUTUBE
        if host in _SOUNDCLOUD_HOSTS:
            return Platform.SOUNDCLOUD
        if host in _INSTAGRAM_HOSTS:
            return Platform.INSTAGRAM
        return None

    @classmethod
    def _path_matches(cls, platform: Platform, parsed) -> bool:
        # Playlists are not single-media downloads.
        if platform is Platform.YOUTUBE and parsed.path.rstrip("/") == "/playlist":
            return False
        path = parsed.path
        query = parsed.query or ""
        for pattern in cls._path_patterns[platform]:
            if pattern.match(path):
                if platform is Platform.YOUTUBE and path == "/watch":
                    # /watch is only valid with a video id.
                    if "v=" not in query:
                        return False
                if platform is Platform.YOUTUBE and parsed.hostname in {"youtu.be", "youtube.com", "www.youtube.com", "music.youtube.com"} and path.count("/") == 1 and path != "/watch":
                    # youtu.be/<id> is fine; a bare youtube.com/<id> is not.
                    if parsed.hostname != "youtu.be":
                        return False
                return True
        return False

    @classmethod
    def _detect_platform(cls, url: str) -> Optional[Platform]:
        """
        Detect platform from URL.

        Args:
            url: URL to analyze

        Returns:
            Platform enum value or None if not detected
        """
        parsed = cls.parse(url)
        return parsed.platform if parsed.is_valid else None

    @classmethod
    def validate(cls, url: str) -> bool:
        """
        Quick validation check.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid and supported
        """
        parsed = cls.parse(url)
        return parsed.is_valid

    @classmethod
    def get_platform_id(cls, url: str) -> str:
        """
        Get platform identifier for URL.

        Args:
            url: URL to analyze

        Returns:
            Platform identifier string

        Raises:
            PlatformNotSupportedError: If platform is not supported
        """
        parsed = cls.parse(url)

        if not parsed.is_valid or parsed.platform is None:
            raise PlatformNotSupportedError(
                parsed.error or "Unsupported platform",
                url=url,
            )

        return parsed.platform.value
