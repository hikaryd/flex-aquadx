# AquaDX Telegram bot

Telegram bot that uses `flex-aquadx` for player profiles, recent-score cards, and comparing `/mine` on the same chart after `/rs`.

## Commands

- `/profile username` — bind or show your AquaDX profile.
- `/rs [username] [index]` — send a PNG card for a recent play. If `username` is omitted, the bound profile is used. The chart/difficulty is stored per chat.
- `/mine [username]` — after `/rs`, send your score card on the same chart/difficulty. If `username` is omitted, the bound profile is used.

The bot registers Telegram command hints for private chats and groups via `setMyCommands`.

By default state is stored in local SQLite. If `STORAGE_API_BASE` and `STORAGE_API_TOKEN` are set, the bot also uses the Cloudflare Worker/KV storage API as primary portable state for linked profiles and `/rs` → `/mine` chat context, with SQLite as fallback/cache for smooth migration between bot deployments.

## Env

```env
BOT_TOKEN=123456:telegram-token
AQUADX_API_BASE=http://127.0.0.1:8017
AQUADX_BOT_DB=/opt/aquadx-tg-bot/aquadx_bot.sqlite3
LOG_LEVEL=INFO
# optional portable state, compatible with maimaibot-storage Worker + KV
STORAGE_API_BASE=https://example-worker.workers.dev
STORAGE_API_TOKEN=shared-secret
STORAGE_API_TIMEOUT=10
```

## Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install 'python-telegram-bot>=21,<22' 'httpx>=0.27'
BOT_TOKEN=... AQUADX_API_BASE=http://127.0.0.1:8017 python bot.py
```
