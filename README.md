# Enterprise Downloader Bot

High-reliability, enterprise-grade Telegram bot for downloading media from YouTube, SoundCloud, and Instagram.

## System Architecture

```
Telegram API
    │
Telegram Bot Layer (/bot/handlers, /bot/middlewares, /bot/keyboards)
    │
Services Layer (/bot/services)
    │
Downloader Abstraction Layer (/bot/downloader)
    │
Infrastructure Layer (/infrastructure)
    │
Core Layer (/core)
```

## Features

- Multi-platform support: YouTube, SoundCloud, Instagram
- Format selection: Audio (MP3) or Video (MP4/WebM)
- Quality options: Best, 1080p, 720p, 480p
- Playlist/album support
- Fully async architecture with asyncio
- Per-user queue isolation with backpressure
- Exponential backoff retry logic
- Rate limiting per user
- Optional user whitelist
- Structured JSON logging
- Graceful shutdown
- Automatic temp file cleanup

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Create temp storage
mkdir -p data/storage/temp
```

## Configuration

See `.env.example` for all configuration options.

**Required:**
- `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather

**Optional:**
- `ALLOWED_USERS`: Comma-separated Telegram user IDs
- `YTDLP_COOKIES_PATH`: Path to cookies.txt
- `YTDLP_PROXY`: Proxy URL if needed
- `MAX_FILE_SIZE_MB`: Max file size for upload (default: 50)
- `RATE_LIMIT_REQUESTS`: Max requests per window (default: 10)
- `SENTRY_DSN`: Sentry DSN for error tracking

## Usage

```bash
python -m bot.main
```

1. Send `/start` to your bot
2. Send a supported URL
3. Select format (Audio/Video)
4. Select quality (for video)
5. Wait for download

## Supported Platforms

| Platform | Content Types |
|----------|--------------|
| YouTube | Videos, Playlists, YouTube Music |
| SoundCloud | Tracks, Sets, Playlists |
| Instagram | Reels, Posts, Carousels |

## Deployment

### Linux Production

```bash
# Install dependencies
sudo apt update
sudo apt install python3.10 python3.10-venv ffmpeg

# Setup systemd service
sudo nano /etc/systemd/system/downloader-bot.service
```

### aaPanel

1. Upload project to `/www/wwwroot/downloader-bot/`
2. Install Python 3.10 via aaPanel
3. Create virtual environment
4. Install dependencies
5. Configure environment variables
6. Set up systemd service

## Troubleshooting

### FFmpeg not found
```bash
sudo apt install ffmpeg  # Ubuntu/Debian
```

### Download fails with timeout
- Increase `DOWNLOAD_TIMEOUT_SECONDS` in .env
- Check network connectivity
- Update yt-dlp: `pip install --upgrade yt-dlp`

### File too large for Telegram
- Bot automatically provides download link for files > 50MB
- Increase `MAX_FILE_SIZE_MB` in .env (Telegram limit is 50MB)

### Rate limited by platform
- Bot uses exponential backoff and will retry
- Consider adding `YTDLP_PROXY` for better reliability

## License

Proprietary - All rights reserved
