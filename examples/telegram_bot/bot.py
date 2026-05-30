from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from telegram import BotCommand, Update
from telegram.constants import BotCommandScopeType, ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

API_BASE = os.getenv("AQUADX_API_BASE", "http://127.0.0.1:8017").rstrip("/")
DB_PATH = Path(os.getenv("AQUADX_BOT_DB", "/opt/aquadx-tg-bot/aquadx_bot.sqlite3"))
TIMEOUT = httpx.Timeout(35.0, connect=10.0)
STORAGE_API_BASE = os.getenv("STORAGE_API_BASE", "").rstrip("/")
STORAGE_API_TOKEN = os.getenv("STORAGE_API_TOKEN", "")
STORAGE_TIMEOUT = httpx.Timeout(float(os.getenv("STORAGE_API_TIMEOUT", "10")), connect=5.0)

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
            create table if not exists message_score_context (
              chat_id integer not null,
              message_id integer not null,
              music_id integer not null,
              difficulty text not null,
              title text not null,
              artist text not null,
              source_username text not null,
              updated_at text not null default current_timestamp,
              primary key(chat_id, message_id)
            );
            """
        )
        conn.commit()


def set_profile_local(tg_user_id: int, username: str) -> None:
    with closing(db()) as conn:
        conn.execute(
            "insert into profiles(tg_user_id, aquadx_username) values(?, ?) "
            "on conflict(tg_user_id) do update set aquadx_username=excluded.aquadx_username, updated_at=current_timestamp",
            (tg_user_id, username),
        )
        conn.commit()


def get_profile_local(tg_user_id: int) -> str | None:
    with closing(db()) as conn:
        row = conn.execute("select aquadx_username from profiles where tg_user_id=?", (tg_user_id,)).fetchone()
        return str(row[0]) if row else None


def get_all_profiles_local() -> list[str]:
    with closing(db()) as conn:
        rows = conn.execute("select aquadx_username from profiles order by updated_at desc").fetchall()
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        username = str(row[0]).strip()
        key = username.casefold()
        if username and key not in seen:
            seen.add(key)
            out.append(username)
    return out


def set_last_map_local(chat_id: int, last: LastMap) -> None:
    with closing(db()) as conn:
        conn.execute(
            "insert into chat_last_map(chat_id, music_id, difficulty, title, artist, source_username) values(?, ?, ?, ?, ?, ?) "
            "on conflict(chat_id) do update set music_id=excluded.music_id, difficulty=excluded.difficulty, "
            "title=excluded.title, artist=excluded.artist, source_username=excluded.source_username, updated_at=current_timestamp",
            (chat_id, last.music_id, last.difficulty, last.title, last.artist, last.source_username),
        )
        conn.commit()


def get_last_map_local(chat_id: int) -> LastMap | None:
    with closing(db()) as conn:
        row = conn.execute("select * from chat_last_map where chat_id=?", (chat_id,)).fetchone()
        if not row:
            return None
        return LastMap(int(row["music_id"]), str(row["difficulty"]), str(row["title"]), str(row["artist"]), str(row["source_username"]))


def set_message_map_local(chat_id: int, message_id: int, last: LastMap) -> None:
    with closing(db()) as conn:
        conn.execute(
            "insert into message_score_context(chat_id, message_id, music_id, difficulty, title, artist, source_username) "
            "values(?, ?, ?, ?, ?, ?, ?) "
            "on conflict(chat_id, message_id) do update set music_id=excluded.music_id, difficulty=excluded.difficulty, "
            "title=excluded.title, artist=excluded.artist, source_username=excluded.source_username, updated_at=current_timestamp",
            (chat_id, message_id, last.music_id, last.difficulty, last.title, last.artist, last.source_username),
        )
        conn.commit()


def get_message_map_local(chat_id: int, message_id: int) -> LastMap | None:
    with closing(db()) as conn:
        row = conn.execute(
            "select * from message_score_context where chat_id=? and message_id=?",
            (chat_id, message_id),
        ).fetchone()
        if not row:
            return None
        return LastMap(int(row["music_id"]), str(row["difficulty"]), str(row["title"]), str(row["artist"]), str(row["source_username"]))


def storage_enabled() -> bool:
    return bool(STORAGE_API_BASE and STORAGE_API_TOKEN)


async def storage_request(method: str, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not storage_enabled():
        return None
    try:
        async with httpx.AsyncClient(timeout=STORAGE_TIMEOUT) as client:
            r = await client.request(
                method,
                f"{STORAGE_API_BASE}{path}",
                headers={"Authorization": f"Bearer {STORAGE_API_TOKEN}"},
                json=json_body,
            )
            r.raise_for_status()
            return r.json()
    except Exception as exc:
        log.warning("storage %s %s failed: %s", method, path, exc)
        return None


async def set_profile(tg_user_id: int, username: str) -> None:
    set_profile_local(tg_user_id, username)
    await storage_request("PUT", f"/linked-profile/{tg_user_id}", {"username": username})


async def get_profile(tg_user_id: int) -> str | None:
    data = await storage_request("GET", f"/linked-profile/{tg_user_id}")
    username = (data or {}).get("username")
    if username:
        set_profile_local(tg_user_id, str(username))
        return str(username)
    username = get_profile_local(tg_user_id)
    if username:
        await storage_request("PUT", f"/linked-profile/{tg_user_id}", {"username": username})
    return username


def last_map_to_context(last: LastMap) -> dict[str, Any]:
    return {
        "music_id": last.music_id,
        "difficulty": last.difficulty,
        "title": last.title,
        "artist": last.artist,
        "source_username": last.source_username,
    }


def last_map_from_context(value: dict[str, Any] | None) -> LastMap | None:
    if not isinstance(value, dict):
        return None
    try:
        return LastMap(
            int(value["music_id"]),
            str(value["difficulty"]),
            str(value.get("title") or f"musicId {value['music_id']}"),
            str(value.get("artist") or ""),
            str(value.get("source_username") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


async def set_last_map(chat_id: int, message_id: int, last: LastMap) -> None:
    set_last_map_local(chat_id, last)
    set_message_map_local(chat_id, message_id, last)
    context_payload = last_map_to_context(last)
    await storage_request("PUT", f"/score-context/{chat_id}/{message_id}", context_payload)
    await storage_request("PUT", f"/last-target/chat/{chat_id}", {"chat_id": chat_id, "message_id": message_id})


async def get_message_map(chat_id: int, message_id: int) -> LastMap | None:
    context = await storage_request("GET", f"/score-context/{chat_id}/{message_id}")
    last = last_map_from_context((context or {}).get("context") if isinstance(context, dict) else None)
    if last:
        set_message_map_local(chat_id, message_id, last)
        return last
    return get_message_map_local(chat_id, message_id)


async def get_last_map(chat_id: int, reply_to_message_id: int | None = None) -> LastMap | None:
    if reply_to_message_id is not None:
        last = await get_message_map(chat_id, reply_to_message_id)
        if last:
            return last
    target = await storage_request("GET", f"/last-target/chat/{chat_id}")
    target_payload = (target or {}).get("target") if isinstance(target, dict) else None
    if isinstance(target_payload, dict) and target_payload.get("message_id") is not None:
        context = await storage_request("GET", f"/score-context/{chat_id}/{target_payload['message_id']}")
        last = last_map_from_context((context or {}).get("context") if isinstance(context, dict) else None)
        if last:
            set_last_map_local(chat_id, last)
            return last
    last = get_last_map_local(chat_id)
    return last

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
        "`/mine` — твой скор на карте из последнего `/rs` в этом чате\n"
        "`/leaderboard` или `/lb` — общий лидерборд привязанных профилей"
    )


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    usernames = get_all_profiles_local()
    current = await get_profile(update.effective_user.id)
    if current and current.casefold() not in {u.casefold() for u in usernames}:
        usernames.insert(0, current)
    if not usernames:
        await update.message.reply_text("В базе ещё нет привязанных профилей. Используй `/profile username`.")
        return

    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    title = update.effective_chat.title or update.effective_user.full_name or "MaiMai leaderboard"
    query = urlencode({"usernames": ",".join(usernames), "title": title, "scale": "1"})
    try:
        png = await api_png(f"/v1/players/-/maimai/leaderboard/card.png?{query}")
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"AquaDX не смог собрать leaderboard ({e.response.status_code}).")
        return
    await update.message.reply_photo(photo=BytesIO(png), caption=f"Leaderboard · {len(usernames)} profiles")


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = context.args[0] if context.args else await get_profile(user_id)
    if not username:
        await update.message.reply_text(need_profile_text())
        return
    try:
        data = await api_json(f"/v1/players/{quote(username)}")
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"Не нашёл профиль `{username}` ({e.response.status_code}).")
        return
    if context.args:
        await set_profile(user_id, username)

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
    default = await get_profile(update.effective_user.id)
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
        last_map = LastMap(music_id, diff, title, artist, username)
        png = await api_png(f"/v1/players/{quote(username)}/maimai/recent/card.png?index={index}&theme=dark&scale=1")
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"AquaDX вернул ошибку {e.response.status_code} для `{username}`.")
        return
    caption = f"`{username}` · {title} [{diff}]\nТеперь любой с привязанным профилем может написать `/mine`."
    sent = await update.message.reply_photo(photo=BytesIO(png), caption=caption)
    await set_last_map(update.effective_chat.id, sent.message_id, last_map)


async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_to_message_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
    last = await get_last_map(update.effective_chat.id, reply_to_message_id)
    if not last:
        await update.message.reply_text("Сначала в этом чате надо вызвать `/rs`, чтобы выбрать карту.")
        return
    username = context.args[0] if context.args else await get_profile(update.effective_user.id)
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
        BotCommand("leaderboard", "общий лидерборд привязанных профилей"),
        BotCommand("lb", "короткая команда лидерборда"),
    ]
    await app.bot.set_my_commands(commands)
    await app.bot.set_my_commands(commands, scope={"type": BotCommandScopeType.ALL_GROUP_CHATS})
    await app.bot.set_my_commands(commands, scope={"type": BotCommandScopeType.ALL_PRIVATE_CHATS})
    me = await app.bot.get_me()
    log.info("bot started as @%s, api=%s, storage=%s", me.username, API_BASE, "enabled" if storage_enabled() else "disabled")


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
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("lb", leaderboard))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
