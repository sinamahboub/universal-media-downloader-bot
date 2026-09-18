# Telegram Media Downloader Bot

Enterprise-grade Telegram bot for downloading media from YouTube, SoundCloud, and Instagram. Built with Python 3.10+, featuring async architecture, rate limiting, queue isolation, and comprehensive error handling.

## Features

- **Multi-platform support**: YouTube (videos, playlists, YouTube Music), SoundCloud (tracks, sets, playlists), Instagram (Reels, Posts, Carousels)
- **Format selection**: Audio (MP3) or Video (MP4/WebM)
- **Quality options**: Best, 1080p, 720p, 480p
- **Async architecture**: Full asyncio-based design for high concurrency
- **Per-user queue isolation**: Each user gets their own download queue with backpressure
- **Rate limiting**: Configurable per-user rate limits to prevent abuse
- **User whitelist**: Optional Telegram user ID whitelist for private bots
- **Structured logging**: JSON-formatted structured logs for production monitoring
- **Graceful shutdown**: Clean resource cleanup on termination
- **Automatic temp file cleanup**: Temporary files are automatically removed after processing
- **Single instance lock**: Prevents multiple bot instances from running simultaneously
- **FFmpeg integration**: Automatic format conversion when FFmpeg is available

## Prerequisites

- Python 3.10 or higher
- FFmpeg (optional but recommended for audio extraction and format conversion)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

## Installation

```bash
# Clone the repository
git clone https://github.com/sinamahboub/universal-media-downloader-bot.git
cd downloader-bot

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\\Scripts\\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings. At minimum, you must set:
   - `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather

### Required Settings

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_USERS` | (empty) | Comma-separated Telegram user IDs. If empty, all users are allowed. |
| `APP_ENV` | `development` | Application environment (`development` or `production`) |
| `DEBUG` | `false` | Enable debug logging |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MAX_FILE_SIZE_MB` | `50` | Maximum file size for direct Telegram upload (Telegram limit is 50MB) |
| `RATE_LIMIT_REQUESTS` | `10` | Max requests per rate limit window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window in seconds |
| `DOWNLOAD_TIMEOUT_SECONDS` | `300` | Download timeout in seconds |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Max concurrent downloads per user |
| `YTDLP_FORMAT` | `bestaudio/best` | yt-dlp format selection string |
| `YTDLP_COOKIES_PATH` | (empty) | Path to cookies.txt for authenticated requests |
| `YTDLP_PROXY` | (empty) | Proxy URL (e.g., `socks5://127.0.0.1:1080`) |
| `WORKER_POOL_SIZE` | `5` | Number of worker threads |
| `RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts for failed downloads |
| `WORKER_CONCURRENCY` | `1` | Worker concurrency for deployment |

### Observability

- `SENTRY_DSN`: Sentry DSN for error tracking (optional)
- `ENABLE_SENTRY`: Enable Sentry integration (optional)

## Usage

```bash
python -m bot.main
```

1. Send `/start` to your bot on Telegram
2. Send a supported URL (YouTube, SoundCloud, or Instagram)
3. Select format (Audio or Video)
4. For video, select quality (Best, 1080p, 720p, 480p)
5. Wait for the download to complete

## Supported Platforms

| Platform | Content Types |
|----------|--------------|
| YouTube | Videos, Playlists, YouTube Music |
| SoundCloud | Tracks, Sets, Playlists |
| Instagram | Reels, Posts, Carousels |

## Project Structure

```
downloader-bot/
+-- bot/
¦   +-- __init__.py
¦   +-- main.py                 # Application entry point
¦   +-- downloader/             # Platform-specific download implementations
¦   ¦   +-- __init__.py
¦   ¦   +-- base.py
¦   ¦   +-- factory.py
¦   ¦   +-- youtube.py
¦   ¦   +-- soundcloud.py
¦   ¦   +-- instagram.py
¦   +-- handlers/               # Telegram update handlers
¦   ¦   +-- __init__.py
¦   ¦   +-- callback.py
¦   ¦   +-- message.py
¦   +-- keyboards/              # Inline keyboard builders
¦   ¦   +-- __init__.py
¦   ¦   +-- inline.py
¦   ¦   +-- layouts.py
¦   +-- middlewares/             # Telegram middlewares
¦   ¦   +-- __init__.py
¦   ¦   +-- auth.py
¦   ¦   +-- rate_limit.py
¦   +-- services/               # Business logic services
¦       +-- __init__.py
¦       +-- media_service.py
¦       +-- url_parser.py
+-- core/
¦   +-- __init__.py
¦   +-- config.py               # Pydantic configuration management
¦   +-- exceptions.py           # Centralized exception hierarchy
¦   +-- logger.py               # Structured JSON logging
+-- data/
¦   +-- storage/
¦       +-- temp/               # Temporary download storage
+-- deploy/
¦   +-- downloader-bot.service  # Systemd service file
+-- infrastructure/
¦   +-- __init__.py
¦   +-- cache.py                # In-memory caching
¦   +-- lock.py                 # Single-instance file lock
¦   +-- queue.py                # Async job queue system
¦   +-- storage.py              # File lifecycle management
+-- tests/
¦   +-- __init__.py
¦   +-- integration/
¦   ¦   +-- __init__.py
¦   +-- unit/
¦       +-- __init__.py
¦       +-- test_exceptions.py
¦       +-- test_url_parser.py
+-- .env.example                # Environment template
+-- .gitignore                  # Git ignore rules
+-- LICENSE                     # Proprietary license
+-- README.md                   # This file
+-- pyproject.toml              # Modern Python packaging configuration
+-- requirements.txt            # Pinned dependencies
```

## Deployment

### Linux with Systemd

```bash
# Install system dependencies
sudo apt update
sudo apt install python3.10 python3.10-venv ffmpeg

# Copy and edit the service file
sudo nano /etc/systemd/system/downloader-bot.service
```

### Docker (Coming Soon)

Docker support is planned for a future release.

## Troubleshooting

### FFmpeg not found
FFmpeg is optional but recommended for audio extraction and format conversion.
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```
Without FFmpeg, the bot will download files in their original format.

### Bot token invalid
Ensure your `TELEGRAM_BOT_TOKEN` is correct. The bot validates the token on startup and will exit with an error if it's invalid.

### Download fails with timeout
- Increase `DOWNLOAD_TIMEOUT_SECONDS` in `.env`
- Check network connectivity
- Consider setting `YTDLP_PROXY` if you're behind a proxy

### File too large for Telegram
- Files larger than `MAX_FILE_SIZE_MB` will be uploaded to Telegram as documents
- Telegram's official limit for media is 50MB
- Increase `MAX_FILE_SIZE_MB` if needed (files will be sent as documents)

### Rate limited by platform
- The bot implements exponential backoff and will automatically retry
- Consider adding `YTDLP_COOKIES_PATH` for authenticated requests
- Use `YTDLP_PROXY` for better reliability

## Known Limitations

### YouTube Restrictions
- YouTube may block downloads from certain IP ranges or regions
- Age-restricted videos require a cookies.txt file configured via `YTDLP_COOKIES_PATH`
- Some videos may be geo-restricted; using a proxy via `YTDLP_PROXY` may help
- YouTube frequently changes their API; keep `yt-dlp` updated for best results
- Live streams and premieres are not supported

### General Limitations
- Maximum concurrent downloads per user is limited by `MAX_CONCURRENT_DOWNLOADS`
- Very large playlists may take significant time to process
- Some platforms may require authentication cookies for full access

## Development

### Running Tests
```bash
pytest
```

### Code Quality
```bash
# Linting
ruff check .

# Type checking
mypy .
```

## License

Proprietary - All rights reserved.

## Contributing

This is an internal project. Contributions are welcome via internal pull requests.
