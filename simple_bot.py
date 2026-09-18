"""
Simple working bot based on reference implementation.
"""

import os
import logging
import asyncio
import tempfile
import shutil
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ Token not found!")

BASE_DIR = Path(__file__).parent
DOWNLOAD_PATH = BASE_DIR / "data" / "storage" / "temp"
DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    await update.message.reply_text(
        "🎵 Welcome! Send me a URL from YouTube, SoundCloud, or Instagram."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command."""
    await update.message.reply_text(
        "📖 Send me a media URL and I'll download it for you."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel command."""
    context.user_data["cancelled"] = True
    await update.message.reply_text("✅ Cancelled.")


async def download_media(url: str, output_dir: Path, format_type: str) -> Path:
    """Download media using yt-dlp."""
    ydl_opts = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    
    loop = asyncio.get_event_loop()
    def do_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return Path(ydl.prepare_filename(info)).with_suffix(".mp3")
    
    return await loop.run_in_executor(None, do_download)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    text = update.message.text.strip()
    status_msg = await update.message.reply_text("🔍 Processing...")
    context.user_data["cancelled"] = False
    
    try:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            file_path = await download_media(text, temp_dir, "audio")
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            if size_mb > 50:
                await status_msg.edit_text(f"⚠️ File too large: {size_mb:.1f}MB")
                file_path.unlink()
                return
            
            await status_msg.edit_text("📤 Sending...")
            with open(file_path, "rb") as media:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=media,
                    caption="✅ Downloaded!"
                )
            await status_msg.delete()
            logger.info(f"✅ Success: {file_path.name}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logger.error(f"Failed: {e}")
        await status_msg.edit_text(f"❌ Failed: {str(e)[:200]}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Error handler."""
    logger.error(f"Error: {context.error}")


def main():
    """Main entry point."""
    print("🚀 Starting bot...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("✅ Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
