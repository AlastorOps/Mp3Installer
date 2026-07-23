import os
import re
import logging
import shutil
import tempfile

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 8080))

# Set to False after the first message is handled, so we can warn the user
# once that Render's free tier may have just cold-started the container.
just_booted = True

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
        "Send me a YouTube link and I'll send back the audio as an MP3.\n\n"
        "If I don't respond right away, I may be waking up from sleep — "
        "just wait 20-30 seconds and I'll catch up."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global just_booted
    if just_booted:
        await update.message.reply_text(
            " I was asleep to save resources — I'm back online! Working on your request now..."
        )
        just_booted = False

    text = update.message.text or ""
    match = YOUTUBE_REGEX.search(text)
    if not match:
        await update.message.reply_text("That doesn't look like a YouTube link. Try again!")
        return

    url = match.group(0)
    status_msg = await update.message.reply_text("Link found! Fetching video info...")

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

        await status_msg.edit_text("Downloading and converting to MP3... this may take a moment.")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "audio")
        except Exception as e:
            logger.exception("Download failed")
            await status_msg.edit_text(f"Sorry, couldn't process that link: {e}")
            return

        await status_msg.edit_text(f"Downloaded \"{title}\"! Preparing file...")

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

        await status_msg.edit_text(f"Uploading \"{title}\" ({size_mb:.1f} MB)...")
        with open(mp3_path, "rb") as audio_file:
            await update.message.reply_audio(audio=audio_file, title=title)
        await status_msg.edit_text(f"Done! Enjoy \"{title}\".")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Set the TELEGRAM_BOT_TOKEN environment variable first.")
    if not WEBHOOK_URL:
        raise RuntimeError(
            "Set the WEBHOOK_URL environment variable (or rely on Render's "
            "auto-populated RENDER_EXTERNAL_URL) to your service's public URL."
        )

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Use the bot token as the URL path so only requests that know it are accepted.
    url_path = BOT_TOKEN
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}/{url_path}"

    logger.info("Bot started, listening for webhook updates on port %s...", PORT)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=url_path,
        webhook_url=full_webhook_url,
    )


if __name__ == "__main__":
    main()