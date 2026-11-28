"""
Environment configuration management.

Uses Pydantic Settings for validation, type safety, and .env support.
All environment variables are centralized here for maintainability.

Settings are lazy: importing this module never touches the environment
and never raises. Call :func:`get_settings` to build (and cache) the
settings object; the bot token itself is validated in ``bot.main`` so
that a missing or malformed token fails with a clear message at
startup instead of an import-time traceback.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation and type safety."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application metadata
    APP_NAME: str = "downloader-bot"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Telegram Bot Configuration. Empty by default on purpose: the
    # token is validated explicitly in bot.main so importing this
    # module (or running the test suite) never crashes for a missing
    # token.
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Bot token from @BotFather",
    )

    # Optional user whitelist (comma-separated Telegram user IDs).
    # None means every user is allowed.
    ALLOWED_USERS: list[int] | None = Field(
        default=None,
        description="Comma-separated list of allowed Telegram user IDs. If None, all users allowed.",
    )

    # Rate limiting configuration
    RATE_LIMIT_REQUESTS: int = Field(default=10, description="Max requests per time window")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, description="Rate limit window in seconds")

    # File handling configuration
    MAX_FILE_SIZE_MB: int = Field(default=50, description="Max file size in MB for Telegram upload")
    TEMP_STORAGE_PATH: Path = Field(
        default=Path("data/storage/temp"),
        description="Temporary file storage directory",
    )
    MAX_CONCURRENT_DOWNLOADS: int = Field(default=3, description="Max concurrent downloads per user")
    DOWNLOAD_TIMEOUT_SECONDS: int = Field(default=300, description="Download timeout in seconds")

    # yt-dlp configuration
    YTDLP_FORMAT: str = Field(
        default="bestaudio/best",
        description="Default yt-dlp format selection",
    )
    YTDLP_COOKIES_PATH: Path | None = Field(
        default=None,
        description="Optional path to cookies.txt file for authenticated requests",
    )
    YTDLP_PROXY: str | None = Field(
        default=None,
        description="Optional proxy URL (e.g., socks5://127.0.0.1:1080)",
    )

    # Worker pool configuration
    WORKER_POOL_SIZE: int = Field(default=5, description="Number of download worker processes")
    JOB_QUEUE_MAX_SIZE: int = Field(default=100, description="Max jobs in the queue")

    # Retry configuration
    RETRY_MAX_ATTEMPTS: int = Field(default=3, description="Max retry attempts for transient failures")
    RETRY_BASE_DELAY: float = Field(default=1.0, description="Base delay in seconds for exponential backoff")
    RETRY_MAX_DELAY: float = Field(default=60.0, description="Max delay in seconds for backoff")

    # Deployment configuration
    WORKER_CONCURRENCY: int = Field(default=1, description="Number of concurrent bot workers")

    @field_validator("ALLOWED_USERS", mode="before")
    @classmethod
    def parse_allowed_users(cls, value: str | list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [int(uid) for uid in value]
        if isinstance(value, str):
            if value.strip() == "":
                return None
            try:
                return [int(uid.strip()) for uid in value.split(",") if uid.strip()]
            except ValueError as exc:
                raise ValueError("ALLOWED_USERS must be comma-separated integers") from exc
        raise ValueError("ALLOWED_USERS must be comma-separated integers")

    @field_validator("TEMP_STORAGE_PATH", mode="before")
    @classmethod
    def ensure_absolute_path(cls, value: Path | str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            # config.py lives in <repo>/core, so the repo root is its
            # parent directory (parent.parent). A previous version used
            # parent.parent.parent and resolved temp storage one level
            # above the repository.
            base = Path(__file__).resolve().parent.parent
            path = base / path
        return path.resolve()

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return upper

    @property
    def temp_storage_path_exists(self) -> bool:
        return self.TEMP_STORAGE_PATH.exists()

    def ensure_temp_storage(self) -> None:
        """Create temp storage directory if it does not exist."""
        self.TEMP_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build (once) and return the application settings.

    Lazy on purpose: importing ``core.config`` must never fail, even
    with no ``.env`` file and no token. The token is validated later,
    in ``bot.main``.
    """
    settings = Settings()
    settings.ensure_temp_storage()
    return settings


def reset_settings_cache() -> None:
    """Drop the cached settings (used by the test suite)."""
    get_settings.cache_clear()


def __getattr__(name: str):
    # Backwards compatibility: ``from core.config import settings``
    # keeps working, but resolves lazily through get_settings().
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
