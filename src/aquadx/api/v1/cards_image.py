"""/v1/players/{u}/maimai/recent/card.png, /v1/players/{u}/maimai/rating/card.png — PNG-карточки."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import Response as RawResponse

from aquadx.api.deps import get_cache, get_client, music_lookup
from aquadx.api.errors import NotFoundError
from aquadx.cache.base import Cache
from aquadx.clients.aquadx import AquadxClient
from aquadx.mappers.maimai import map_rating_frame, map_recent_plays
from aquadx.models.domain import MusicMeta
from aquadx.render import renderer
from aquadx.render.cache_keys import compute_etag, image_cache_key
from aquadx.render.jacket_loader import fetch_jacket, fetch_jackets
from aquadx.render.templates.leaderboard import LeaderboardEntry, LeaderboardInput
from aquadx.render.templates.leaderboard import render as render_leaderboard
from aquadx.render.templates.rating_frame import RatingFrameInput, RatingItem
from aquadx.render.templates.rating_frame import render as render_rating
from aquadx.render.templates.track_result import TrackResultInput
from aquadx.render.templates.track_result import render as render_track
from aquadx.settings import Settings, get_settings

router = APIRouter(prefix="/v1/players", tags=["cards"])

MAI2_PREFIX = "/api/v2/game/mai2"


def _cache_headers(etag: str, settings: Settings, *, hit: bool) -> dict[str, str]:
    return {
        "Content-Type": "image/png",
        "Cache-Control": f"public, max-age={settings.cache_ttl_image_seconds}",
        "ETag": f'"{etag}"',
        "Vary": "Accept",
        "x-cache": "HIT" if hit else "MISS",
    }


async def _png_response(
    cache: Cache,
    settings: Settings,
    endpoint: str,
    etag_payload: Any,
    build_png: Callable[[], Awaitable[bytes]],
    *,
    scale: int,
) -> Response:
    etag = compute_etag(endpoint, etag_payload, scale=scale)
    key = image_cache_key(endpoint, etag)
    cached = await cache.get(key)
    if cached is not None:
        return RawResponse(
            content=cached, status_code=200, headers=_cache_headers(etag, settings, hit=True)
        )
    png = await build_png()
    await cache.set(key, png, ttl=settings.cache_ttl_image_seconds)
    return RawResponse(
        content=png, status_code=200, headers=_cache_headers(etag, settings, hit=False)
    )


@router.get(
    "/{username}/maimai/recent/card.png",
    summary="PNG-карточка одного недавнего скора",
    response_class=Response,
)
async def recent_card(
    username: str,
    index: int = Query(0, ge=0, le=199),
    scale: int = Query(1, ge=1, le=2),
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> Response:
    raw = await client.get(f"{MAI2_PREFIX}/recent", params={"username": username})
    rows = raw if isinstance(raw, list) else []
    plays = map_recent_plays(rows, music_lookup=lookup)
    if index >= len(plays):
        raise NotFoundError(f"Recent play index out of range: {index} >= {len(plays)}")
    play = plays[index]
    previous_rating = _previous_after_rating(plays, index)

    # Деталь профиля — для шапки. Best-effort: при сбое — None.
    summary_raw = await client.get(f"{MAI2_PREFIX}/user-summary", params={"username": username})
    rating = 0
    if isinstance(summary_raw, dict):
        rating = int(summary_raw.get("rating") or 0)

    jacket_url = play.music.jacket if play.music and play.music.jacket else ""
    jacket = await fetch_jacket(jacket_url, settings=settings, cache=cache) if jacket_url else None

    inp = TrackResultInput(
        title=(
            play.music.title
            if play.music and play.music.title
            else f"musicId {play.music.id if play.music else '?'}"
        ),
        artist=(play.music.artist if play.music and play.music.artist else ""),
        difficulty=str(play.difficulty),
        level=float(
            play.music.levels[_safe_level_index(play.difficulty, play.music.levels)]
            if (play.music and play.music.levels)
            else 0.0
        ),
        chart_tag="DX",
        achievement=float(play.achievement),
        rank=str(play.rank),
        rating=rating,
        max_combo=int(play.max_combo or 0),
        fast=int(play.fast or 0),
        late=int(play.late or 0),
        deluxe_score=int(play.deluxe_score or 0),
        deluxe_max=int(play.deluxe_score or 0),
        rating_delta=(int(play.after_rating) - previous_rating if play.after_rating and previous_rating is not None else 0),
        judgements=_judgements_for_render(play),
        note_accuracy=_note_accuracy_for_render(play),
        play_date=str(play.user_play_date or play.play_date or ""),
        jacket=jacket,
    )

    etag_payload = inp.__dict__.copy()
    etag_payload.pop("jacket", None)

    async def _build() -> bytes:
        return await renderer.run_render(lambda: render_track(inp))

    return await _png_response(
        cache,
        settings,
        endpoint=f"recent/{username}/{index}",
        etag_payload=etag_payload,
        build_png=_build,
        scale=scale,
    )


def _previous_after_rating(plays: list[object], index: int) -> int | None:
    """Rating before this play: next older recent row's after_rating.

    `map_recent_plays` sorts newest-first, so for plays[index] the row at
    index+1 is the immediately previous play available in the recent window.
    The profile summary usually equals the latest afterRating, so subtracting
    from summary hides `/rs` rating gains for index=0.
    """
    for older in plays[index + 1 :]:
        after_rating = getattr(older, "after_rating", None)
        if after_rating is not None:
            return int(after_rating)
    return None


def _judgements_for_render(play: object) -> list[tuple[str, int]]:
    """RecentPlay.judgements → list[(label, value)] для шаблона."""
    j = getattr(play, "judgements", None)
    if j is None:
        return [("CRIT", 0), ("PERFECT", 0), ("GREAT", 0), ("GOOD", 0), ("MISS", 0)]
    return [
        ("CRIT", j.crit),
        ("PERFECT", j.perfect),
        ("GREAT", j.great),
        ("GOOD", j.good),
        ("MISS", j.miss),
    ]


def _note_accuracy_for_render(play: object) -> list[tuple[str, float, int]]:
    """RecentPlay.note_accuracy → list[(label, accuracy_frac, crit_count)]."""
    n = getattr(play, "note_accuracy", None)
    if n is None:
        return [
            ("TAP", 1.0, 0),
            ("HOLD", 1.0, 0),
            ("SLIDE", 1.0, 0),
            ("TOUCH", 1.0, 0),
            ("BREAK", 1.0, 0),
        ]

    def _row(label: str, stats: object) -> tuple[str, float, int]:
        total = getattr(stats, "total", 0) or 0
        crit = getattr(stats, "crit", 0) or 0
        perfect = getattr(stats, "perfect", 0) or 0
        # Полоса = (CRIT + PERFECT) / total — «как хорошо сыграно».
        # Справа показываем total по типу нот (как в живом maimaibot:
        # TAP 483, HOLD 53, SLIDE 60, TOUCH 102, BREAK 42).
        frac = (crit + perfect) / total if total > 0 else 0.0
        return label, frac, total

    return [
        _row("TAP", n.tap),
        _row("HOLD", n.hold),
        _row("SLIDE", n.slide),
        _row("TOUCH", n.touch),
        _row("BREAK", n.break_),
    ]


def _safe_level_index(difficulty: str, levels: list[float]) -> int:
    """Индекс уровня в music.levels по имени difficulty."""
    order = ("BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER", "UTAGE")
    try:
        i = order.index(difficulty)
    except ValueError:
        return 0
    return min(i, len(levels) - 1) if levels else 0


@router.get(
    "/{username}/maimai/scores/card.png",
    summary="PNG-карточка конкретного скора по musicId/difficulty",
    response_class=Response,
)
async def score_card(
    username: str,
    musicId: int = Query(..., ge=1),
    difficulty: str | None = Query(None),
    theme: str = Query("dark", pattern="^(dark|light)$"),
    scale: int = Query(1, ge=1, le=2),
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> Response:
    raw = await client.post(
        f"{MAI2_PREFIX}/user-music-from-list",
        params={"username": username},
        json=[musicId],
    )
    plays = map_recent_plays(raw if isinstance(raw, list) else [], music_lookup=lookup)
    if difficulty:
        plays = [p for p in plays if str(p.difficulty).upper() == difficulty.upper()]
    if not plays:
        raise NotFoundError(f"No score for {username}: musicId={musicId}, difficulty={difficulty or '*'}")
    play = max(plays, key=lambda p: float(p.achievement or 0))

    # `user-music-from-list` returns the durable best score, but not detailed
    # judgement/note-type breakdown. The public `recent` endpoint is backed by
    # the playlog repo and exposes historical playlog rows with those fields, so
    # `/mine` cards can best-effort attach the closest detailed playlog for the
    # same chart. We keep achievement/rank from the best score and render
    # judgements, FAST/LATE and play date from the matching playlog when found.
    detailed_play = await _matching_playlog_for_score(
        client=client,
        username=username,
        music_id=musicId,
        difficulty=str(play.difficulty),
        achievement=float(play.achievement or 0),
        lookup=lookup,
    )

    summary_raw = await client.get(f"{MAI2_PREFIX}/user-summary", params={"username": username})
    rating = int(summary_raw.get("rating") or 0) if isinstance(summary_raw, dict) else 0
    jacket_url = play.music.jacket if play.music and play.music.jacket else ""
    jacket = await fetch_jacket(jacket_url, settings=settings, cache=cache) if jacket_url else None

    inp = TrackResultInput(
        title=(play.music.title if play.music and play.music.title else f"musicId {musicId}"),
        artist=(play.music.artist if play.music and play.music.artist else ""),
        difficulty=str(play.difficulty),
        level=float(
            play.music.levels[_safe_level_index(str(play.difficulty), play.music.levels)]
            if (play.music and play.music.levels)
            else 0.0
        ),
        chart_tag="DX",
        achievement=float(play.achievement),
        rank=str(play.rank),
        rating=rating,
        max_combo=int(play.max_combo or (detailed_play.max_combo if detailed_play else 0) or 0),
        fast=int((detailed_play.fast if detailed_play else None) or 0),
        late=int((detailed_play.late if detailed_play else None) or 0),
        deluxe_score=int(play.deluxe_score or 0),
        deluxe_max=int(play.deluxe_score or 0),
        rating_delta=0,
        judgements=_judgements_for_render(detailed_play or play),
        note_accuracy=_note_accuracy_for_render(detailed_play or play),
        play_date=str(
            (detailed_play.user_play_date if detailed_play else None)
            or (detailed_play.play_date if detailed_play else None)
            or play.user_play_date
            or play.play_date
            or ""
        ),
        jacket=jacket,
    )
    etag_payload = inp.__dict__.copy()
    etag_payload.pop("jacket", None)

    async def _build() -> bytes:
        return await renderer.run_render(lambda: render_track(inp))

    return await _png_response(
        cache,
        settings,
        endpoint=f"score/{username}/{musicId}/{difficulty or ''}",
        etag_payload=etag_payload,
        build_png=_build,
        scale=scale,
    )


async def _matching_playlog_for_score(
    *,
    client: AquadxClient,
    username: str,
    music_id: int,
    difficulty: str,
    achievement: float,
    lookup: dict[int, MusicMeta],
) -> object | None:
    """Find a detailed historical playlog row for a best-score card."""
    try:
        raw = await client.get(f"{MAI2_PREFIX}/recent", params={"username": username})
    except Exception:
        return None
    rows = raw if isinstance(raw, list) else []
    detailed = [
        p
        for p in map_recent_plays(rows, music_lookup=lookup)
        if p.music
        and p.music.id == music_id
        and str(p.difficulty).upper() == difficulty.upper()
        and (p.judgements is not None or p.note_accuracy is not None)
    ]
    if not detailed:
        return None
    return min(
        detailed,
        key=lambda p: (abs(float(p.achievement or 0) - achievement), -float(p.achievement or 0)),
    )


@router.get(
    "/{username}/maimai/rating/card.png",
    summary="PNG-карточка best35/best15 рейтинг-фрейма",
    response_class=Response,
)
async def rating_card(
    username: str,
    scale: int = Query(1, ge=1, le=2),
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> Response:
    raw = await client.get(f"{MAI2_PREFIX}/user-rating", params={"username": username})
    if not isinstance(raw, dict):
        raise NotFoundError(f"No rating data for {username}")
    frame = map_rating_frame(raw, music_lookup=lookup)

    summary_raw = await client.get(f"{MAI2_PREFIX}/user-summary", params={"username": username})
    rating = 0
    if isinstance(summary_raw, dict):
        rating = int(summary_raw.get("rating") or 0)

    def _item(t) -> RatingItem:  # type: ignore[no-untyped-def]
        return RatingItem(
            music_id=(t.music.id if t.music else 0),
            title=(t.music.title if t.music and t.music.title else ""),
            level=float(
                t.music.levels[_safe_level_index(str(t.difficulty), t.music.levels)]
                if (t.music and t.music.levels)
                else 0.0
            ),
            difficulty=str(t.difficulty),
            achievement=float(t.achievement),
            rank=str(t.rank),
            rating_contribution=int(t.rating_contribution or 0),
        )

    b35_items = [_item(t) for t in frame.best35]
    b15_items = [_item(t) for t in frame.best15]

    # Параллельная загрузка всех jacket'ов.
    urls = [
        (t.music.jacket if t.music and t.music.jacket else "")
        for t in [*frame.best35, *frame.best15]
    ]
    jackets = await fetch_jackets(urls, settings=settings, cache=cache)

    inp = RatingFrameInput(
        username=username,
        rating=rating,
        b35_sum=sum(it.rating_contribution for it in b35_items),
        b15_sum=sum(it.rating_contribution for it in b15_items),
        b35=b35_items,
        b15=b15_items,
        jackets_b35=jackets[: len(b35_items)],
        jackets_b15=jackets[len(b35_items) :],
    )

    etag_payload = {
        "username": username,
        "rating": rating,
        "b35": [it.__dict__ for it in b35_items],
        "b15": [it.__dict__ for it in b15_items],
    }

    async def _build() -> bytes:
        return await renderer.run_render(lambda: render_rating(inp))

    return await _png_response(
        cache,
        settings,
        endpoint=f"rating/{username}",
        etag_payload=etag_payload,
        build_png=_build,
        scale=scale,
    )


@router.get(
    "/-/maimai/leaderboard/card.png",
    summary="PNG-лидерборд нескольких maimai-профилей",
    response_class=Response,
)
async def leaderboard_card(
    usernames: str = Query(
        ...,
        min_length=1,
        max_length=512,
        description="Comma-separated AquaDX usernames, max 20 unique values",
    ),
    title: str = Query("MaiMai leaderboard", max_length=80),
    scale: int = Query(1, ge=1, le=2),
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> Response:
    names: list[str] = []
    seen: set[str] = set()
    for raw_name in usernames.split(","):
        name = raw_name.strip()
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            names.append(name)
            if len(names) >= 20:
                break
    if not names:
        raise NotFoundError("No usernames for leaderboard")

    gate = asyncio.Semaphore(4)

    async def _load_one(name: str) -> LeaderboardEntry | None:
        try:
            async with gate:
                summary_raw, rating_raw = await asyncio.gather(
                    client.get(f"{MAI2_PREFIX}/user-summary", params={"username": name}),
                    client.get(f"{MAI2_PREFIX}/user-rating", params={"username": name}),
                )
        except Exception:
            return None
        rating = int(summary_raw.get("rating") or 0) if isinstance(summary_raw, dict) else 0
        b35_sum = 0
        b15_sum = 0
        best_count = 0
        if isinstance(rating_raw, dict):
            frame = map_rating_frame(rating_raw, music_lookup=lookup)
            b35_sum = sum(int(t.rating_contribution or 0) for t in frame.best35)
            b15_sum = sum(int(t.rating_contribution or 0) for t in frame.best15)
            best_count = len(frame.best35) + len(frame.best15)
        return LeaderboardEntry(username=name, rating=rating, rank=0, b35_sum=b35_sum, b15_sum=b15_sum, best_count=best_count)

    loaded = await asyncio.gather(*(_load_one(name) for name in names))
    entries = sorted((entry for entry in loaded if entry is not None), key=lambda e: e.rating, reverse=True)
    if not entries:
        raise NotFoundError("No valid profiles for leaderboard")
    ranked = [
        LeaderboardEntry(
            username=entry.username,
            rating=entry.rating,
            rank=i + 1,
            b35_sum=entry.b35_sum,
            b15_sum=entry.b15_sum,
            best_count=entry.best_count,
        )
        for i, entry in enumerate(entries)
    ]
    inp = LeaderboardInput(title=title, entries=ranked)
    etag_payload = {"title": title, "entries": [entry.__dict__ for entry in ranked]}

    async def _build() -> bytes:
        return await renderer.run_render(lambda: render_leaderboard(inp))

    return await _png_response(
        cache,
        settings,
        endpoint="leaderboard/" + ",".join(names),
        etag_payload=etag_payload,
        build_png=_build,
        scale=scale,
    )
