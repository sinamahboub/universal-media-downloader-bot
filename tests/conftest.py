"""Shared test fixtures.

The bot must be testable without a real Telegram token or a .env
file: a well-formed fake token and a temporary storage directory are
set here, before any test module imports the bot code. Proxy
environment variables are also cleared: httpx (used by
python-telegram-bot) parses them when building the application, and
bracketed IPv6 entries in no_proxy make it raise InvalidURL.
"""

import os
import tempfile

# A fake token with the real shape ("<bot-id>:<secret>") so token
# validation passes without ever touching the network.
os.environ.setdefault(
    "TELEGRAM_BOT_TOKEN",
    "123456789:AAFakeTokenForTests1234567890abcdefghij",
)
os.environ.setdefault("ALLOWED_USERS", "")

for _var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
):
    os.environ.pop(_var, None)

os.environ.setdefault(
    "TEMP_STORAGE_PATH",
    os.path.join(tempfile.mkdtemp(prefix="umd-test-"), "temp"),
)

import pytest  # noqa: E402

from core.config import reset_settings_cache  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_settings():
    """Give every test a fresh (uncached) settings object."""
    reset_settings_cache()
    yield
    reset_settings_cache()
