# KizarichiBot

A Telegram bot that converts YouTube links into downloadable MP3 audio.

## Features

- Send a YouTube link, get back an MP3 of the audio
- Built with `python-telegram-bot` (long polling) and `yt-dlp`
- Audio extraction via `ffmpeg`
- Includes a built-in HTTP health-check endpoint for always-on hosting (e.g. Render)

## Requirements

- Python 3.12+
- `ffmpeg` installed and on PATH (or set `FFMPEG_LOCATION`)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your values:
   ```
   cp .env.example .env
   ```
3. Run the bot:
   ```
   python bot.py
   ```

## Environment Variables

| Variable            | Required | Description                                                                 |
|---------------------|----------|-------------------------------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN` | Yes      | Your bot's token from BotFather                                              |
| `FFMPEG_LOCATION`    | No       | Path to ffmpeg's `bin` folder, if it isn't on PATH                           |
| `YT_COOKIES_FILE`    | No       | Path to a YouTube `cookies.txt` file, used to bypass YouTube bot-detection    |
| `PORT`               | No       | Port for the health-check server (defaults to `8080`; set by Render automatically) |
| `YTDLP_DEBUG`        | No       | Set to `1` to enable verbose yt-dlp logging for troubleshooting             |

## YouTube Cookies

YouTube sometimes blocks download requests from cloud/datacenter IPs with a
"Sign in to confirm you're not a bot" error. To work around this, export a
`cookies.txt` file from a logged-in YouTube session (e.g. using the
"Get cookies.txt LOCALLY" browser extension) and point `YT_COOKIES_FILE` at it.

Use a throwaway Google account for this, not your main one — never commit
`cookies.txt` to git or share its contents anywhere.

## Deploying on Render (free tier)

This repo includes a `Dockerfile` that installs `ffmpeg` and `deno` (required
by yt-dlp to solve YouTube's JS challenges) alongside the bot.

1. Push this repo to GitHub.
2. On Render: **New → Web Service**, connect the repo, environment = **Docker**.
3. Add your environment variables (see table above) in the Render dashboard.
4. If using cookies, upload `cookies.txt` under **Secret Files** and set
   `YT_COOKIES_FILE=/etc/secrets/cookies.txt`.
5. Deploy. Render's free Web Service tier spins down after ~15 minutes of no
   HTTP traffic — use an external uptime pinger (e.g. UptimeRobot) to hit your
   Render URL every 5-10 minutes to keep the bot running continuously.

## Notes

- Telegram bots can only upload files up to 50 MB; longer videos will be rejected after download.
- Only one instance of this bot can poll Telegram at a time — running it locally while it's also deployed will cause a `Conflict` error.
