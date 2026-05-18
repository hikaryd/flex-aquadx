"""/v1/maimai/ranking — paginated leaderboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from aquadx.api.deps import get_cache, get_client
from aquadx.api.errors import NotFoundError
from aquadx.cache.base import Cache, cached_call
from aquadx.clients.aquadx import AquadxClient
from aquadx.models.domain import RankingEntry, RankingPage, ResponseEnvelope
from aquadx.settings import Settings, get_settings

router = APIRouter(prefix="/v1/maimai/ranking", tags=["maimai"])

MAI2_PREFIX = "/api/v2/game/mai2"


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_entry(raw: dict[str, Any]) -> RankingEntry:
    return RankingEntry(
        rank=_as_int(raw.get("rank")),
        username=str(raw.get("username") or ""),
        name=str(raw.get("name") or ""),
        rating=_as_int(raw.get("rating")),
        last_seen=raw.get("lastSeen") if isinstance(raw.get("lastSeen"), str) else None,
        accuracy=_as_float(raw.get("accuracy")),
        full_combo=raw.get("fullCombo") if isinstance(raw.get("fullCombo"), int) else None,
        all_perfect=raw.get("allPerfect") if isinstance(raw.get("allPerfect"), int) else None,
    )


@router.get(
    "",
    response_model=ResponseEnvelope[RankingPage],
    summary="Paginated maimai ranking",
)
async def ranking(
    response: Response,
    page: int = Query(0, ge=0),
    size: int = Query(100, ge=1, le=500),
    client: AquadxClient = Depends(get_client),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[RankingPage]:
    async def _load() -> RankingPage:
        raw = await client.get(f"{MAI2_PREFIX}/ranking", params={"page": page})
        rows = raw if isinstance(raw, list) else []
        entries = [_to_entry(r) for r in rows if isinstance(r, dict)]
        return RankingPage(page=page, size=size, total=len(entries), entries=entries[:size])

    value, state = await cached_call(
        cache,
        f"maimai-ranking|{page}|{size}",
        settings.cache_ttl_ranking_seconds,
        _load,
    )
    response.headers["x-cache"] = state
    envelope = ResponseEnvelope[RankingPage](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope


@router.get(
    "/{username}",
    response_model=ResponseEnvelope[RankingEntry],
    summary="Single player's ranking",
)
async def ranking_by_username(
    username: str,
    response: Response,
    client: AquadxClient = Depends(get_client),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[RankingEntry]:
    async def _load() -> RankingEntry:
        raw = await client.get(f"{MAI2_PREFIX}/ranking")
        rows = raw if isinstance(raw, list) else []
        for r in rows:
            if isinstance(r, dict) and str(r.get("username")) == username:
                return _to_entry(r)
        raise NotFoundError(f"Player not in ranking: {username}")

    value, state = await cached_call(
        cache,
        f"maimai-ranking-by-user|{username}",
        settings.cache_ttl_ranking_seconds,
        _load,
    )
    response.headers["x-cache"] = state
    envelope = ResponseEnvelope[RankingEntry](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope
