"""/v1/players/{username}/maimai/scores — пакетный запрос скоров по списку musicId."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from aquadx.api.deps import get_cache, get_client, music_lookup
from aquadx.cache.base import Cache, cached_envelope
from aquadx.clients.aquadx import AquadxClient
from aquadx.mappers.maimai import map_recent_plays
from aquadx.models.domain import MusicMeta, RecentPlay, ResponseEnvelope
from aquadx.settings import Settings, get_settings

router = APIRouter(tags=["scores"])

MAI2_PREFIX = "/api/v2/game/mai2"


@router.get(
    "/v1/players/{username}/maimai/scores",
    response_model=ResponseEnvelope[list[RecentPlay]],
    summary="Пакетный запрос скоров по списку musicId",
)
async def user_music_from_list(
    username: str,
    response: Response,
    musicIds: str = Query(..., description="ID треков через запятую"),
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
    ids_sorted = sorted(set(ids))  # каноничный ключ кэша: порядок и дубли не влияют

    async def _load() -> list[RecentPlay]:
        # Контракт upstream (Kotlin `userMusicFromList(@RP username, @RB musicList: List<Int>)`):
        #   - username идёт как request param (query/form);
        #   - musicList — само JSON-тело: сырой массив int, НЕ обёрнутый в объект.
        # Отправка `{"username":..., "musicList":[...]}` в теле вернёт 400.
        raw = await client.post(
            f"{MAI2_PREFIX}/user-music-from-list",
            params={"username": username},
            json=ids_sorted,
        )
        rows = raw if isinstance(raw, list) else []
        return map_recent_plays(rows, music_lookup=lookup)

    cache_key = f"maimai-scores|{username}|{','.join(map(str, ids_sorted))}"
    return await cached_envelope(
        cache, cache_key, settings.cache_ttl_player_seconds, _load, response
    )
