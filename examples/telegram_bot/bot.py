from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from telegram import BotCommand, Update
from telegram.constants import BotCommandScopeType, ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

API_BASE = os.getenv("AQUADX_API_BASE", "http://127.0.0.1:8017").rstrip("/")
DB_PATH = Path(os.getenv("AQUADX_BOT_DB", "/opt/aquadx-tg-bot/aquadx_bot.sqlite3"))
TIMEOUT = httpx.Timeout(35.0, connect=10.0)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aquadx-tg-bot")


@dataclass
class LastMap:
    music_id: int
    difficulty: str
    title: str
    artist: str
    source_username: str


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(db()) as conn:
        conn.executescript(
            """
            create table if not exists profiles (
              tg_user_id integer primary key,
              aquadx_username text not null,
              updated_at text not null default current_timestamp
            );
            create table if not exists chat_last_map (
              chat_id integer primary key,
              music_id integer not null,
              difficulty text not null,
              title text not null,
              artist text not null,
              source_username text not null,
              updated_at text not null default current_timestamp
            );
            """
        )
        conn.commit()


def set_profile(tg_user_id: int, username: str) -> None:
    with closing(db()) as conn:
        conn.execute(
            "insert into profiles(tg_user_id, aquadx_username) values(?, ?) "
            "on conflict(tg_user_id) do update set aquadx_username=excluded.aquadx_username, updated_at=current_timestamp",
            (tg_user_id, username),
        )
        conn.commit()


def get_profile(tg_user_id: int) -> str | None:
    with closing(db()) as conn:
        row = conn.execute("select aquadx_username from profiles where tg_user_id=?", (tg_user_id,)).fetchone()
        return str(row[0]) if row else None


def set_last_map(chat_id: int, last: LastMap) -> None:
    with closing(db()) as conn:
        conn.execute(
            "insert into chat_last_map(chat_id, music_id, difficulty, title, artist, source_username) values(?, ?, ?, ?, ?, ?) "
            "on conflict(chat_id) do update set music_id=excluded.music_id, difficulty=excluded.difficulty, "
            "title=excluded.title, artist=excluded.artist, source_username=excluded.source_username, updated_at=current_timestamp",
            (chat_id, last.music_id, last.difficulty, last.title, last.artist, last.source_username),
        )
        conn.commit()


def get_last_map(chat_id: int) -> LastMap | None:
    with closing(db()) as conn:
        row = conn.execute("select * from chat_last_map where chat_id=?", (chat_id,)).fetchone()
        if not row:
            return None
        return LastMap(int(row["music_id"]), str(row["difficulty"]), str(row["title"]), str(row["artist"]), str(row["source_username"]))


def parse_user_and_index(args: list[str], default_username: str | None) -> tuple[str | None, int]:
    username = default_username
    index = 0
    if args:
        if args[0].isdigit():
            index = int(args[0])
        else:
            username = args[0]
            if len(args) > 1 and args[1].isdigit():
                index = int(args[1])
    return username, index


def need_profile_text() -> str:
    return "Сначала привяжи AquaDX-профиль: `/profile твой_username`"


async def api_json(path: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{API_BASE}{path}")
        r.raise_for_status()
        return r.json()


async def api_png(path: str) -> bytes:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{API_BASE}{path}")
        r.raise_for_status()
        return r.content


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "AquaDX bot готов.\n"
        "Команды:\n"
        "`/profile username` — привязать/посмотреть профиль\n"
        "`/rs [username] [index]` — карточка последней игры\n"
        "`/mine` — твой скор на карте из последнего `/rs` в этом чате"
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = context.args[0] if context.args else get_profile(user_id)
    if not username:
        await update.message.reply_text(need_profile_text())
        return
    try:
        data = await api_json(f"/v1/players/{quote(username)}")
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"Не нашёл профиль `{username}` ({e.response.status_code}).")
        return
    if context.args:
        set_profile(user_id, username)

    player = data.get("data", {})
    mai = player.get("maimai") or {}
    caption_parts = [f"Профиль `{username}`"]
    if context.args:
        caption_parts.append("привязан ✅")
    if mai:
        caption_parts.append(f"rating: {mai.get('rating') or '—'}")

    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        png = await api_png(f"/v1/players/{quote(username)}/maimai/rating/card.png?theme=dark&scale=1")
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(
            "\n".join(caption_parts) + f"\nНе смог получить B50-картинку ({e.response.status_code})."
        )
        return
    await update.message.reply_photo(photo=BytesIO(png), caption=" · ".join(caption_parts))


async def rs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    default = get_profile(update.effective_user.id)
    username, index = parse_user_and_index(context.args, default)
    if not username:
        await update.message.reply_text(need_profile_text())
        return
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        recent = await api_json(f"/v1/players/{quote(username)}/maimai/recent?limit={max(index + 1, 1)}")
        plays = recent.get("data") or []
        if index >= len(plays):
            await update.message.reply_text(f"У `{username}` нет recent-скора с index={index}.")
            return
        play = plays[index]
        music = play.get("music") or {}
        music_id = int(music.get("id"))
        diff = str(play.get("difficulty") or "")
        title = str(music.get("title") or f"musicId {music_id}")
        artist = str(music.get("artist") or "")
        set_last_map(update.effective_chat.id, LastMap(music_id, diff, title, artist, username))
        png = await api_png(f"/v1/players/{quote(username)}/maimai/recent/card.png?index={index}&theme=dark&scale=1")
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"AquaDX вернул ошибку {e.response.status_code} для `{username}`.")
        return
    caption = f"`{username}` · {title} [{diff}]\nТеперь любой с привязанным профилем может написать `/mine`."
    await update.message.reply_photo(photo=BytesIO(png), caption=caption)


async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    last = get_last_map(update.effective_chat.id)
    if not last:
        await update.message.reply_text("Сначала в этом чате надо вызвать `/rs`, чтобы выбрать карту.")
        return
    username = context.args[0] if context.args else get_profile(update.effective_user.id)
    if not username:
        await update.message.reply_text(need_profile_text())
        return
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        png = await api_png(
            f"/v1/players/{quote(username)}/maimai/scores/card.png?musicId={last.music_id}&difficulty={quote(last.difficulty)}&theme=dark&scale=1"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await update.message.reply_text(f"У `{username}` не нашёл скора на {last.title} [{last.difficulty}].")
        else:
            await update.message.reply_text(f"AquaDX вернул ошибку {e.response.status_code} для `{username}`.")
        return
    await update.message.reply_photo(photo=BytesIO(png), caption=f"`{username}` на {last.title} [{last.difficulty}]")


async def post_init(app: Application) -> None:
    commands = [
        BotCommand("start", "справка по AquaDX-боту"),
        BotCommand("profile", "показать B50-профиль или привязать username"),
        BotCommand("rs", "показать recent score: /rs [username] [index]"),
        BotCommand("mine", "твой скор на карте из последнего /rs"),
    ]
    await app.bot.set_my_commands(commands)
    await app.bot.set_my_commands(commands, scope={"type": BotCommandScopeType.ALL_GROUP_CHATS})
    await app.bot.set_my_commands(commands, scope={"type": BotCommandScopeType.ALL_PRIVATE_CHATS})
    me = await app.bot.get_me()
    log.info("bot started as @%s, api=%s", me.username, API_BASE)


def main() -> None:
    init_db()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN is required")
    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("rs", rs))
    app.add_handler(CommandHandler("mine", mine))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
