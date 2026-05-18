"""/v1/players/* endpoints: cross-game profile, maimai-specific deep views."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from aquadx.api.deps import get_cache, get_client, music_lookup
from aquadx.api.errors import NotFoundError
from aquadx.cache.base import Cache, cached_call
from aquadx.clients.aquadx import AquadxClient
from aquadx.mappers.maimai import (
    map_favorites,
    map_profile,
    map_rating_frame,
    map_recent_plays,
    map_trend,
)
from aquadx.models.domain import (
    FavoriteEntry,
    GameSummary,
    MaimaiProfile,
    MusicMeta,
    Player,
    RatingFrame,
    RecentPlay,
    ResponseEnvelope,
    TrendPoint,
)
from aquadx.settings import Settings, get_settings

router = APIRouter(prefix="/v1/players", tags=["players"])


MAI2_PREFIX = "/api/v2/game/mai2"
CARD_PREFIX = "/api/v2/card"


async def _user_summary(client: AquadxClient, username: str) -> dict[str, Any]:
    raw = await client.get(f"{MAI2_PREFIX}/user-summary", params={"username": username})
    if not isinstance(raw, dict):
        raise NotFoundError(f"Empty maimai summary for {username}")
    return raw


def _cache_key(*parts: object) -> str:
    return "|".join(str(p) for p in parts)


def _apply_cache_state(response: Response, state: str) -> None:
    response.headers["x-cache"] = state


@router.get(
    "/{username}",
    response_model=ResponseEnvelope[Player],
    summary="Cross-game player profile",
)
async def player(
    username: str,
    response: Response,
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[Player]:
    async def _load() -> Player:
        games_raw = await client.get(f"{CARD_PREFIX}/user-games", params={"username": username})
        games_list = games_raw if isinstance(games_raw, list) else []
        games = [
            GameSummary(
                game=str(g.get("game") or g.get("name") or "unknown"),
                last_seen=g.get("lastSeen") or g.get("lastPlayDate") or g.get("accessTime"),
                rating=g.get("rating"),
                name=g.get("name"),
            )
            for g in games_list
            if isinstance(g, dict)
        ]
        maimai: MaimaiProfile | None
        try:
            summary = await _user_summary(client, username)
            maimai = map_profile(username, summary)
        except NotFoundError:
            maimai = None
        return Player(username=username, games=games, maimai=maimai)

    value, state = await cached_call(
        cache,
        _cache_key("player", username),
        settings.cache_ttl_player_seconds,
        _load,
    )
    _apply_cache_state(response, state)
    envelope = ResponseEnvelope[Player](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope


@router.get(
    "/{username}/maimai",
    response_model=ResponseEnvelope[MaimaiProfile],
    summary="Deep maimai profile (summary + detail)",
)
async def maimai_profile(
    username: str,
    response: Response,
    client: AquadxClient = Depends(get_client),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[MaimaiProfile]:
    async def _load() -> MaimaiProfile:
        summary = await _user_summary(client, username)
        detail = await client.get(f"{MAI2_PREFIX}/user-detail", params={"username": username})
        return map_profile(
            username,
            summary,
            detail if isinstance(detail, dict) else None,
        )

    value, state = await cached_call(
        cache,
        _cache_key("maimai-profile", username),
        settings.cache_ttl_player_seconds,
        _load,
    )
    _apply_cache_state(response, state)
    envelope = ResponseEnvelope[MaimaiProfile](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope


@router.get(
    "/{username}/maimai/rating",
    response_model=ResponseEnvelope[RatingFrame],
    summary="best35 / best15 with inline music meta",
)
async def maimai_rating(
    username: str,
    response: Response,
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[RatingFrame]:
    async def _load() -> RatingFrame:
        raw = await client.get(f"{MAI2_PREFIX}/user-rating", params={"username": username})
        if not isinstance(raw, dict):
            raise NotFoundError(f"No rating data for {username}")
        return map_rating_frame(raw, music_lookup=lookup)

    value, state = await cached_call(
        cache,
        _cache_key("maimai-rating", username),
        settings.cache_ttl_player_seconds,
        _load,
    )
    _apply_cache_state(response, state)
    envelope = ResponseEnvelope[RatingFrame](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope


@router.get(
    "/{username}/maimai/recent",
    response_model=ResponseEnvelope[list[RecentPlay]],
    summary="Recent plays, normalised",
)
async def maimai_recent(
    username: str,
    response: Response,
    limit: int = Query(50, ge=1, le=200),
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[list[RecentPlay]]:
    async def _load() -> list[RecentPlay]:
        raw = await client.get(f"{MAI2_PREFIX}/recent", params={"username": username})
        rows = raw if isinstance(raw, list) else []
        # Cache the full list at max upstream size; slice post-cache so distinct
        # ?limit=N values share one upstream fetch per TTL window.
        return map_recent_plays(rows, music_lookup=lookup, limit=None)

    cached_value, state = await cached_call(
        cache,
        _cache_key("maimai-recent", username),
        settings.cache_ttl_player_seconds,
        _load,
    )
    sliced: list[RecentPlay] = list(cached_value)[:limit]
    _apply_cache_state(response, state)
    envelope = ResponseEnvelope[list[RecentPlay]](data=sliced)
    envelope.meta.cached = state == "HIT"
    return envelope


@router.get(
    "/{username}/maimai/favorites",
    response_model=ResponseEnvelope[list[FavoriteEntry]],
    summary="Favorite tracks",
)
async def maimai_favorites(
    username: str,
    response: Response,
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[list[FavoriteEntry]]:
    async def _load() -> list[FavoriteEntry]:
        raw = await client.get(f"{MAI2_PREFIX}/user-favorite", params={"username": username})
        rows = raw if isinstance(raw, list) else []
        return map_favorites(rows, music_lookup=lookup)

    value, state = await cached_call(
        cache,
        _cache_key("maimai-favorites", username),
        settings.cache_ttl_player_seconds,
        _load,
    )
    _apply_cache_state(response, state)
    envelope = ResponseEnvelope[list[FavoriteEntry]](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope


@router.get(
    "/{username}/maimai/trend",
    response_model=ResponseEnvelope[list[TrendPoint]],
    summary="Rating timeseries",
)
async def maimai_trend(
    username: str,
    response: Response,
    client: AquadxClient = Depends(get_client),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[list[TrendPoint]]:
    async def _load() -> list[TrendPoint]:
        raw = await client.get(f"{MAI2_PREFIX}/trend", params={"username": username})
        rows = raw if isinstance(raw, list) else []
        return map_trend(rows)

    value, state = await cached_call(
        cache,
        _cache_key("maimai-trend", username),
        settings.cache_ttl_player_seconds,
        _load,
    )
    _apply_cache_state(response, state)
    envelope = ResponseEnvelope[list[TrendPoint]](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope
