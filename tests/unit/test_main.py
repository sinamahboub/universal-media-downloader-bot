"""Tests for bot startup: token validation and application wiring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import TelegramError

from bot.main import _post_init, create_bot_application, validate_token
from core.exceptions import ConfigurationError


def test_validate_token_rejects_missing_and_malformed():
    with pytest.raises(ConfigurationError):
        validate_token("")
    with pytest.raises(ConfigurationError):
        validate_token("fake-token")
    with pytest.raises(ConfigurationError):
        validate_token("abc:short")


def test_validate_token_accepts_real_shape():
    validate_token("123456789:AAFakeTokenForTests1234567890abcdefghij")


def test_create_application_with_fake_token_builds_without_network():
    app = create_bot_application()
    assert app.post_init is not None
    # 3 commands + 1 message handler + 3 callback handlers.
    assert len(app.handlers.get(0, [])) == 7


def test_create_application_without_token_fails_cleanly(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    from core.config import reset_settings_cache

    reset_settings_cache()
    with pytest.raises(ConfigurationError):
        create_bot_application()


async def test_post_init_deletes_webhook_and_validates_token():
    bot = SimpleNamespace(
        delete_webhook=AsyncMock(),
        get_me=AsyncMock(return_value=SimpleNamespace(id=1, username="testbot")),
    )
    await _post_init(SimpleNamespace(bot=bot))
    bot.delete_webhook.assert_awaited_once()
    bot.get_me.assert_awaited_once()


async def test_post_init_rejects_bad_token():
    bot = SimpleNamespace(
        delete_webhook=AsyncMock(),
        get_me=AsyncMock(side_effect=TelegramError("Unauthorized")),
    )
    with pytest.raises(ConfigurationError):
        await _post_init(SimpleNamespace(bot=bot))
