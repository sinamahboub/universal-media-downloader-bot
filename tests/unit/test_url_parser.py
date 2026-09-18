
import pytest

from bot.services.url_parser import URLParserService, Platform


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
