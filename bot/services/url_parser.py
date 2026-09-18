"""
URL parsing and validation service.

Handles URL validation, platform detection, and input sanitization
for all supported platforms.
"""

import re
from dataclasses import dataclass
from typing import Optional

from core.config import settings
from core.exceptions import PlatformNotSupportedError, URLValidationError
from core.logger import StructuredLogger

from bot.downloader import DownloaderFactory, PlatformType

logger = StructuredLogger(component="url_parser")


@dataclass
class ParsedURL:
    """Parsed URL information."""

    original_url: str
    normalized_url: str
    platform: PlatformType
    is_valid: bool
    error: Optional[str] = None


class URLParserService:
    """
    Service for parsing and validating media URLs.

    Responsibilities:
    - Validate URL format
    - Detect platform
    - Sanitize input
    - Provide user-friendly error messages
    """

    def __init__(self, downloader_factory: DownloaderFactory | None = None) -> None:
        self._factory = downloader_factory or DownloaderFactory()

    def parse(self, url: str) -> ParsedURL:
        """
        Parse and validate a URL.

        Args:
            url: Raw URL from user input

        Returns:
            ParsedURL with validation results

        Raises:
            URLValidationError: If URL format is invalid
            PlatformNotSupportedError: If platform is not supported
        """
        sanitized = self._sanitize_url(url)

        if not self._is_valid_url_format(sanitized):
            raise URLValidationError(
                "Invalid URL format",
                url=url,
                details={"sanitized_url": sanitized},
            )

        platform = self._factory.detect_platform(sanitized)

        if platform is None:
            supported = ", ".join(self._factory.get_supported_platforms())
            raise PlatformNotSupportedError(
                f"Platform not supported. Supported platforms: {supported}",
                url=url,
            )

        logger.info("url_parsed", url=url, platform=platform.value, valid=True)

        return ParsedURL(
            original_url=url,
            normalized_url=sanitized,
            platform=platform,
            is_valid=True,
        )

    def validate_only(self, url: str) -> bool:
        """
        Quick validation without raising exceptions.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid and supported
        """
        try:
            self.parse(url)
            return True
        except (URLValidationError, PlatformNotSupportedError):
            return False

    def _sanitize_url(self, url: str) -> str:
        """
        Sanitize user-provided URL.

        Args:
            url: Raw URL string

        Returns:
            Sanitized URL
        """
        url = url.strip()
        url = re.sub(r"\s+", "", url)

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def _is_valid_url_format(self, url: str) -> bool:
        """
        Check if URL has valid format.

        Args:
            url: URL to check

        Returns:
            True if URL format is valid
        """
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
            r"localhost|"  # localhost
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        return bool(url_pattern.match(url))

    def get_platform_name(self, platform: PlatformType) -> str:
        """Get human-readable platform name."""
        names = {
            PlatformType.YOUTUBE: "YouTube",
            PlatformType.YOUTUBE_MUSIC: "YouTube Music",
            PlatformType.SOUNDCLOUD: "SoundCloud",
            PlatformType.INSTAGRAM: "Instagram",
            PlatformType.UNKNOWN: "Unknown",
        }
        return names.get(platform, "Unknown")
