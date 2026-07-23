import os
import re
import logging
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

COOKIES_FILE = None
_cookies_source = os.environ.get("YT_COOKIES_FILE")
if _cookies_source:
    COOKIES_FILE = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    shutil.copyfile(_cookies_source, COOKIES_FILE)

YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+"
)

MAX_FILE_SIZE_MB = 50  # Telegram Bot API upload limit for bots


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a YouTube link and I'll send back the audio as an MP3."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = YOUTUBE_REGEX.search(text)
    if not match:
        await update.message.reply_text("That doesn't look like a YouTube link. Try again!")
        return

    url = match.group(0)
    status_msg = await update.message.reply_text("Downloading and converting... this may take a moment.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        outtmpl = os.path.join(tmp_dir, "%(title).100s.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "noplaylist": True,
            "quiet": not os.environ.get("YTDLP_DEBUG"),
            "verbose": bool(os.environ.get("YTDLP_DEBUG")),
            "remote_components": ["ejs:github"],
        }
        ffmpeg_location = os.environ.get("FFMPEG_LOCATION")
        if ffmpeg_location:
            ydl_opts["ffmpeg_location"] = ffmpeg_location

        if COOKIES_FILE:
            ydl_opts["cookiefile"] = COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "audio")
        except Exception as e:
            logger.exception("Download failed")
            await status_msg.edit_text(f"Sorry, couldn't process that link: {e}")
            return

        mp3_path = None
        for f in os.listdir(tmp_dir):
            if f.endswith(".mp3"):
                mp3_path = os.path.join(tmp_dir, f)
                break

        if not mp3_path:
            await status_msg.edit_text("Something went wrong — no audio file was produced.")
            return

        size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(
                f"The audio file is {size_mb:.1f} MB, which is over Telegram's "
                f"{MAX_FILE_SIZE_MB} MB bot upload limit. Try a shorter video."
            )
            return

        await status_msg.edit_text("Uploading...")
        with open(mp3_path, "rb") as audio_file:
            await update.message.reply_audio(audio=audio_file, title=title)
        await status_msg.delete()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Set the TELEGRAM_BOT_TOKEN environment variable first.")

    threading.Thread(target=start_health_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started, polling...")
    app.run_polling()


if __name__ == "__main__":
    main()