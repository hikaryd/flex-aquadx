"""FastAPI dependency injection: AquadxClient, MetaLoader, Cache."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from aquadx.cache.base import Cache
from aquadx.cache.memory import NoopCache, TTLCache
from aquadx.clients.aquadx import AquadxClient
from aquadx.meta.loader import MusicMetaLoader, get_loader
from aquadx.settings import get_settings

_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        backend = get_settings().cache_backend
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
    with contextlib.suppress(Exception):
        await loader.load()
    return loader.all()  # type: ignore[return-value]
