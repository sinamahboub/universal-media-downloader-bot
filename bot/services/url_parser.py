"""
URL parsing and platform detection service.

Analyzes URLs to identify the platform and validate download eligibility.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.exceptions import PlatformNotSupportedError, URLValidationError
from core.logger import StructuredLogger

logger = StructuredLogger(component="url_parser")


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

    # Platform detection patterns
    _patterns = {
        Platform.YOUTUBE: [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
            r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
            r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=[\w-]+",
            r"(?:https?://)?(?:music\.)?youtube\.com/watch\?v=[\w-]+",
            r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+",
        ],
        Platform.SOUNDCLOUD: [
            r"(?:https?://)?(?:www\.)?soundcloud\.com/[\w-]+/[\w-]+",
            r"(?:https?://)?on\.soundcloud\.com/[\w-]+",
            r"(?:https?://)?(?:www\.)?soundcloud\.com/[\w-]+/sets/[\w-]+",
        ],
        Platform.INSTAGRAM: [
            r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv)/[\w-]+",
            r"(?:https?://)?ddinstagram\.com/[\w-]+",
            r"(?:https?://)?(?:www\.)?instagram\.com/[\w-]+/(?:p|reel)/[\w-]+",
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

        # Detect platform
        platform = cls._detect_platform(url)

        if platform is None:
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
    def _detect_platform(cls, url: str) -> Optional[Platform]:
        """
        Detect platform from URL.

        Args:
            url: URL to analyze

        Returns:
            Platform enum value or None if not detected
        """
        for platform, patterns in cls._patterns.items():
            for pattern in patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    logger.debug(
                        "platform_detected",
                        url=url,
                        platform=platform.value,
                    )
                    return platform

        return None

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
