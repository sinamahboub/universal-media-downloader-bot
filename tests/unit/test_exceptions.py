
import pytest

from core.exceptions import (
    DownloaderError,
    URLValidationError,
    PlatformNotSupportedError,
    DownloadFailedError,
    FileSizeLimitExceededError,
    RateLimitExceededError,
)


def test_downloader_error_base():
    error = DownloaderError("test error", code="TEST_CODE")
    assert str(error) == "[TEST_CODE] test error"
    assert error.code == "TEST_CODE"


def test_url_validation_error():
    error = URLValidationError("bad url", url="http://bad")
    assert error.url == "http://bad"
    assert "bad url" in str(error)


def test_platform_not_supported_error():
    error = PlatformNotSupportedError("unsupported", url="http://test", platform="unknown")
    assert error.platform == "unknown"


def test_download_failed_error_with_job_id():
    error = DownloadFailedError("failed", job_id="job-123")
    assert error.job_id == "job-123"


def test_rate_limit_exceeded_error():
    error = RateLimitExceededError("rate limited", user_id=42, retry_after=30)
    assert error.user_id == 42
    assert error.retry_after == 30
