import pytest

from bot.downloader.base import BaseDownloader, Quality


class _Downloader(BaseDownloader):
    async def extract_info(self, url):
        raise NotImplementedError

    async def download(self, url, output_path, format_type="audio", quality="best", job_id=None):
        raise NotImplementedError


def test_quality_from_value_accepts_both_spellings():
    assert Quality.from_value("best") is Quality.BEST
    assert Quality.from_value("1080p") is Quality.P1080
    assert Quality.from_value("1080") is Quality.P1080
    assert Quality.from_value("720p") is Quality.P720
    assert Quality.from_value("720") is Quality.P720
    assert Quality.from_value("480p") is Quality.P480
    assert Quality.from_value("480") is Quality.P480
    assert Quality.from_value(Quality.P720) is Quality.P720


def test_quality_from_value_rejects_unknown():
    with pytest.raises(ValueError):
        Quality.from_value("4k")


def test_video_format_spec_uses_quality():
    downloader = _Downloader()
    assert "height<=1080" in downloader._get_video_format_spec("1080p")
    assert "height<=1080" in downloader._get_video_format_spec("1080")
    assert "height<=720" in downloader._get_video_format_spec("720p")
    assert "height<=480" in downloader._get_video_format_spec("480p")
    assert downloader._get_video_format_spec("best").startswith("bestvideo")


def test_build_ydl_opts_security_keys(tmp_path):
    downloader = _Downloader()
    opts = downloader._build_ydl_opts(tmp_path, "video", "1080p", job_id="job-1")
    assert opts["noplaylist"] is True
    assert opts["max_downloads"] == 1
    assert opts["restrictfilenames"] is True
    assert opts["max_filesize"] == 50 * 1024 * 1024
    assert opts["retries"] == 3
    assert opts["socket_timeout"] == 30
    assert opts["outtmpl"] == str(tmp_path / "job-1_%(id)s.%(ext)s")
    # The output name is the video id, never the user-controlled title.
    assert "%(title)s" not in opts["outtmpl"]
    assert "nocheckcertificate" not in opts


def test_build_ydl_opts_audio_without_job(tmp_path):
    downloader = _Downloader()
    opts = downloader._build_ydl_opts(tmp_path, "audio", "best")
    assert opts["outtmpl"] == str(tmp_path / "%(id)s.%(ext)s")
    assert opts["format"] == "bestaudio/best"


def test_build_ydl_opts_fixes_preferredformat_spelling(tmp_path):
    downloader = _Downloader(ffmpeg_available=True)
    opts = downloader._build_ydl_opts(tmp_path, "video", "best")
    postprocessor = opts["postprocessors"][0]
    assert postprocessor["key"] == "FFmpegVideoConvertor"
    assert postprocessor["preferredformat"] == "mp4"
    assert "preferedformat" not in postprocessor
