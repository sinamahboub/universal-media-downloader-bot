"""Tests for the pending-job registry and the download path."""

from pathlib import Path

import pytest

from bot.downloader.base import BaseDownloader, MediaInfo
from bot.services.media_service import MediaDownloadService
from core.exceptions import FileSizeLimitExceededError
from infrastructure.queue import AsyncDownloadQueue
from infrastructure.storage import StorageManager


class FakeDownloader(BaseDownloader):
    """A downloader that writes a small file instead of hitting the network."""

    def __init__(self, file_size: int = 1234, is_playlist: bool = False):
        super().__init__(ffmpeg_available=False)
        self.platform_name = "youtube"
        self._file_size = file_size
        self._is_playlist = is_playlist
        self.download_called = False

    async def extract_info(self, url: str) -> MediaInfo:
        return MediaInfo(
            title="Fake",
            url=url,
            platform="youtube",
            file_size=self._file_size,
            is_playlist=self._is_playlist,
            playlist_count=3 if self._is_playlist else None,
        )

    async def download(self, url, output_path, format_type="audio", quality="best", job_id=None) -> Path:
        self.download_called = True
        output_path.mkdir(parents=True, exist_ok=True)
        file_path = output_path / f"{job_id or 'x'}_fake.mp3"
        file_path.write_bytes(b"0" * self._file_size)
        return file_path


@pytest.fixture
def service(monkeypatch):
    return MediaDownloadService(
        download_queue=AsyncDownloadQueue(),
        storage_manager=StorageManager(),
        ffmpeg_available=False,
    )


def test_register_pending_gives_unique_job_ids(service):
    job1 = service.register_pending("https://www.youtube.com/watch?v=abc", 111)
    job2 = service.register_pending("https://youtu.be/abc", 111)
    assert job1.job_id != job2.job_id
    assert job1.url != job2.url


def test_pending_job_is_owned_by_its_user(service):
    job = service.register_pending("https://www.youtube.com/watch?v=abc", 111)
    assert service.get_pending_for_user(job.job_id, 111) is job
    assert service.get_pending_for_user(job.job_id, 222) is None
    assert service.pop_pending(job.job_id, 222) is None
    assert service.pop_pending(job.job_id, 111) is job
    assert service.get_pending(job.job_id) is None


def test_register_pending_rejects_invalid_url(service):
    with pytest.raises(Exception):
        service.register_pending("https://example.com/video.mp4", 111)


async def test_cancel_pending_removes_job_and_files(service):
    job = service.register_pending("https://www.youtube.com/watch?v=abc", 111)
    assert await service.cancel_pending(job.job_id, 111) is True
    assert service.get_pending(job.job_id) is None


async def test_process_url_writes_job_scoped_file(service, monkeypatch):
    fake = FakeDownloader()
    monkeypatch.setattr(
        "bot.services.media_service.DownloaderFactory.create",
        lambda platform, ffmpeg_available=True: fake,
    )
    file_path, error = await service.process_url(
        "https://www.youtube.com/watch?v=abc",
        user_id=111,
        format_type="audio",
        quality="best",
        job_id="job-42",
    )
    assert error is None
    assert file_path is not None
    assert file_path.parent.name == "job-42"
    assert file_path.name.startswith("job-42_")
    assert file_path.exists()
    service.cleanup_job_files("job-42")
    assert not file_path.exists()


async def test_process_url_rejects_oversized_file_before_download(service, monkeypatch):
    fake = FakeDownloader(file_size=60 * 1024 * 1024)
    monkeypatch.setattr(
        "bot.services.media_service.DownloaderFactory.create",
        lambda platform, ffmpeg_available=True: fake,
    )
    with pytest.raises(FileSizeLimitExceededError):
        await service.process_url(
            "https://www.youtube.com/watch?v=abc",
            user_id=111,
            job_id="job-99",
        )
    assert fake.download_called is False


async def test_process_url_rejects_playlist(service, monkeypatch):
    fake = FakeDownloader(is_playlist=True)
    monkeypatch.setattr(
        "bot.services.media_service.DownloaderFactory.create",
        lambda platform, ffmpeg_available=True: fake,
    )
    file_path, error = await service.process_url(
        "https://www.youtube.com/watch?v=abc",
        user_id=111,
        job_id="job-100",
    )
    assert file_path is None
    assert error is not None
    assert fake.download_called is False
