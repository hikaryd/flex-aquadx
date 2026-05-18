"""/v1/scores/{playlogId} and /v1/players/{username}/maimai/scores."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from aquadx.api.deps import get_cache, get_client, music_lookup
from aquadx.api.errors import NotFoundError
from aquadx.cache.base import Cache, cached_call
from aquadx.clients.aquadx import AquadxClient
from aquadx.mappers.maimai import map_recent_plays
from aquadx.models.domain import MusicMeta, RecentPlay, ResponseEnvelope
from aquadx.settings import Settings, get_settings

router = APIRouter(tags=["scores"])

MAI2_PREFIX = "/api/v2/game/mai2"


@router.get(
    "/v1/scores/{playlog_id}",
    response_model=ResponseEnvelope[RecentPlay],
    summary="Single playlog detail",
)
async def playlog_detail(
    playlog_id: int,
    response: Response,
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[RecentPlay]:
    async def _load() -> RecentPlay:
        raw = await client.get(f"{MAI2_PREFIX}/playlog", params={"id": playlog_id})
        if not isinstance(raw, dict):
            raise NotFoundError(f"Playlog not found: {playlog_id}")
        mapped = map_recent_plays([raw], music_lookup=lookup)
        if not mapped:
            raise NotFoundError(f"Playlog not parseable: {playlog_id}")
        return mapped[0]

    value, state = await cached_call(
        cache, f"playlog|{playlog_id}", settings.cache_ttl_player_seconds, _load
    )
    response.headers["x-cache"] = state
    envelope = ResponseEnvelope[RecentPlay](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope


@router.get(
    "/v1/players/{username}/maimai/scores",
    response_model=ResponseEnvelope[list[RecentPlay]],
    summary="Bulk score lookup for given musicIds",
)
async def user_music_from_list(
    username: str,
    response: Response,
    musicIds: str = Query(..., description="comma-separated music ids"),
    client: AquadxClient = Depends(get_client),
    lookup: dict[int, MusicMeta] = Depends(music_lookup),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[list[RecentPlay]]:
    ids: list[int] = []
    for token in musicIds.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.append(int(token))
        except ValueError:
            continue
    ids_sorted = sorted(set(ids))  # canonicalise cache key so order/dupes share

    async def _load() -> list[RecentPlay]:
        # Upstream contract (Kotlin `userMusicFromList(@RP username, @RB musicList: List<Int>)`):
        #   - username is a request param (query/form)
        #   - musicList is the JSON BODY itself — a raw array of ints, NOT wrapped in an object.
        # Sending `{"username":..., "musicList":[...]}` as the JSON body gets a 400.
        raw = await client.post(
            f"{MAI2_PREFIX}/user-music-from-list",
            params={"username": username},
            json=ids_sorted,
        )
        rows = raw if isinstance(raw, list) else []
        return map_recent_plays(rows, music_lookup=lookup)

    cache_key = f"maimai-scores|{username}|{','.join(map(str, ids_sorted))}"
    value, state = await cached_call(cache, cache_key, settings.cache_ttl_player_seconds, _load)
    response.headers["x-cache"] = state
    envelope = ResponseEnvelope[list[RecentPlay]](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope
