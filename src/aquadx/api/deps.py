"""FastAPI dependency injection: AquadxClient, MetaLoader, Cache, optional API key auth."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import Header

from aquadx.api.errors import UnauthorizedError
from aquadx.cache.base import Cache
from aquadx.cache.memory import NoopCache, TTLCache
from aquadx.clients.aquadx import AquadxClient
from aquadx.meta.loader import MusicMetaLoader, get_loader
from aquadx.settings import Settings, get_settings

_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        backend = get_settings().cache_backend
        # memory is the default. redis is wired in a follow-up milestone.
        _cache = NoopCache() if backend == "noop" else TTLCache()
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None


async def get_client() -> AsyncIterator[AquadxClient]:
    client = AquadxClient()
    try:
        yield client
    finally:
        await client.aclose()


def get_meta_loader() -> MusicMetaLoader:
    return get_loader()


async def music_lookup() -> dict[int, object]:
    loader = get_meta_loader()
    # Best-effort: never crash a player request if upstream meta is unreachable.
    # The mapper falls back to music=None when missing.
    with contextlib.suppress(Exception):
        await loader.load()
    return loader.all()  # type: ignore[return-value]


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    if not s.api_key:
        return
    if not x_api_key or x_api_key != s.api_key:
        raise UnauthorizedError("Invalid or missing X-API-Key", upstream_status=None)
