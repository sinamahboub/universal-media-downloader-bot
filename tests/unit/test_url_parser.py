
import pytest

from bot.services.url_parser import Platform, URLParserService


class TestURLParserService:
    def setup_method(self):
        self.parser = URLParserService()

    def test_parse_youtube_url(self):
        result = self.parser.parse("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == Platform.YOUTUBE

    def test_parse_youtube_short_url(self):
        result = self.parser.parse("https://youtu.be/dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == Platform.YOUTUBE

    def test_parse_soundcloud_url(self):
        result = self.parser.parse("https://soundcloud.com/artist/track")
        assert result.is_valid
        assert result.platform == Platform.SOUNDCLOUD

    def test_parse_instagram_url(self):
        result = self.parser.parse("https://www.instagram.com/reel/ABC123/")
        assert result.is_valid
        assert result.platform == Platform.INSTAGRAM

    def test_parse_invalid_url(self):
        result = self.parser.parse("not a url")
        assert not result.is_valid
        assert result.error is not None

    def test_parse_empty_url(self):
        result = self.parser.parse("")
        assert not result.is_valid

    def test_parse_youtube_shorts(self):
        result = self.parser.parse("https://www.youtube.com/shorts/dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == Platform.YOUTUBE

    def test_parse_youtube_embed(self):
        result = self.parser.parse("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == Platform.YOUTUBE

    def test_parse_youtube_live(self):
        result = self.parser.parse("https://www.youtube.com/live/dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == Platform.YOUTUBE

    def test_parse_youtube_music(self):
        result = self.parser.parse("https://music.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == Platform.YOUTUBE

    def test_parse_instagram_reels(self):
        result = self.parser.parse("https://www.instagram.com/reels/ABC123/")
        assert result.is_valid
        assert result.platform == Platform.INSTAGRAM

    def test_parse_soundcloud_short_link(self):
        result = self.parser.parse("https://on.soundcloud.com/abc123")
        assert result.is_valid
        assert result.platform == Platform.SOUNDCLOUD

    @pytest.mark.parametrize(
        "url",
        [
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ",  # http, not https
            "https://user:pass@www.youtube.com/watch?v=x",  # userinfo
            "https://www.youtube.com:8443/watch?v=x",  # non-standard port
            "https://www.youtube.com.evil.com/watch?v=x",  # lookalike host
            "https://ddinstagram.com/ABC123",  # third-party mirror
            "https://www.youtube.com/playlist?list=PL123",  # playlist
            "https://www.youtube.com/watch",  # watch without a video id
            "https://m.youtube.com/watch?v=x",  # host not on the allowlist
            "https://www.soundcloud.com/artist/track",  # host not on the allowlist
            "https://example.com/video.mp4",
        ],
    )
    def test_parse_rejects_unsafe_urls(self, url):
        assert not self.parser.parse(url).is_valid

    def test_parse_rejects_overlong_url(self):
        url = "https://www.youtube.com/watch?v=" + "x" * 3000
        assert not self.parser.parse(url).is_valid
