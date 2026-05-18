"""/v1/cards/{cardId} — public card summary."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from aquadx.api.deps import get_cache, get_client
from aquadx.api.errors import NotFoundError
from aquadx.cache.base import Cache, cached_call
from aquadx.clients.aquadx import AquadxClient
from aquadx.models.domain import CardSummary, ResponseEnvelope
from aquadx.settings import Settings, get_settings

router = APIRouter(prefix="/v1/cards", tags=["cards"])

CARD_PREFIX = "/api/v2/card"


def _normalise(raw: dict[str, Any]) -> CardSummary:
    card = raw.get("card") if isinstance(raw.get("card"), dict) else raw
    if not isinstance(card, dict):
        card = {}
    return CardSummary(
        card_id=card.get("cardId") or card.get("luid") or card.get("id"),
        ext_id=card.get("extId"),
        access_time=card.get("accessTime"),
        raw=raw if isinstance(raw, dict) else None,
    )


@router.get(
    "/{card_id}",
    response_model=ResponseEnvelope[CardSummary],
    summary="Public card summary",
)
async def card_summary(
    card_id: str,
    response: Response,
    client: AquadxClient = Depends(get_client),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ResponseEnvelope[CardSummary]:
    async def _load() -> CardSummary:
        raw = await client.get(f"{CARD_PREFIX}/user-games", params={"username": card_id})
        if isinstance(raw, dict):
            return _normalise(raw)
        if isinstance(raw, list):
            return CardSummary(card_id=card_id, raw={"games": raw})
        raise NotFoundError(f"Card not found: {card_id}")

    value, state = await cached_call(
        cache, f"card|{card_id}", settings.cache_ttl_player_seconds, _load
    )
    response.headers["x-cache"] = state
    envelope = ResponseEnvelope[CardSummary](data=value)
    envelope.meta.cached = state == "HIT"
    return envelope
