"""/v1/players/{u}/maimai/recent/card.png, /v1/players/{u}/maimai/rating/card.png — PNG-карточки."""

from __future__ import annotations

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
    theme: str,
    scale: int,
) -> Response:
    etag = compute_etag(endpoint, etag_payload, theme=theme, scale=scale)
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
    theme: str = Query("dark", pattern="^(dark|light)$"),
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
        rating_delta=int(play.after_rating or 0) - rating if play.after_rating else 0,
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
        theme=theme,
        scale=scale,
    )


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
        # Accuracy fraction: считаем «как хорошо» по тиру (CRIT + PERFECT) / total.
        frac = (crit + perfect) / total if total > 0 else 0.0
        return label, frac, crit

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
    "/{username}/maimai/rating/card.png",
    summary="PNG-карточка best35/best15 рейтинг-фрейма",
    response_class=Response,
)
async def rating_card(
    username: str,
    theme: str = Query("dark", pattern="^(dark|light)$"),
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
        theme=theme,
        scale=scale,
    )
