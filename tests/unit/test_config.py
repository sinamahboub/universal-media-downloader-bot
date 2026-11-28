from pathlib import Path

import pytest

from core.config import Settings, get_settings, reset_settings_cache


def test_importing_config_without_token_does_not_crash(monkeypatch):
    """Importing core.config (or core) must never crash for a missing token."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    reset_settings_cache()
    settings = get_settings()
    assert settings.TELEGRAM_BOT_TOKEN == ""


def test_allowed_users_parses_comma_separated_ids():
    settings = Settings(TELEGRAM_BOT_TOKEN="x", ALLOWED_USERS="111, 222")
    assert settings.ALLOWED_USERS == [111, 222]


def test_allowed_users_empty_means_everyone():
    assert Settings(TELEGRAM_BOT_TOKEN="x", ALLOWED_USERS="").ALLOWED_USERS is None
    assert Settings(TELEGRAM_BOT_TOKEN="x", ALLOWED_USERS=None).ALLOWED_USERS is None


def test_allowed_users_rejects_non_integers():
    with pytest.raises(ValueError):
        Settings(TELEGRAM_BOT_TOKEN="x", ALLOWED_USERS="abc")


def test_temp_storage_path_is_inside_the_repo():
    settings = Settings(TELEGRAM_BOT_TOKEN="x", TEMP_STORAGE_PATH="data/storage/temp")
    repo_root = Path(__file__).resolve().parents[2]
    assert str(settings.TEMP_STORAGE_PATH).startswith(str(repo_root))
    assert settings.TEMP_STORAGE_PATH == repo_root / "data" / "storage" / "temp"


def test_temp_storage_path_absolute_is_kept(tmp_path):
    settings = Settings(TELEGRAM_BOT_TOKEN="x", TEMP_STORAGE_PATH=str(tmp_path))
    assert settings.TEMP_STORAGE_PATH == tmp_path.resolve()


def test_log_level_is_normalized():
    assert Settings(TELEGRAM_BOT_TOKEN="x", LOG_LEVEL="debug").LOG_LEVEL == "DEBUG"
    with pytest.raises(ValueError):
        Settings(TELEGRAM_BOT_TOKEN="x", LOG_LEVEL="verbose")
