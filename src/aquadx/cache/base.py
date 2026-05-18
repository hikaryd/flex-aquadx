from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    @property
    def backend(self) -> str: ...


CacheState = tuple[Any, str]  # (value, x-cache header)


async def cached_call(
    cache: Cache,
    key: str,
    ttl: int,
    loader: Callable[[], Awaitable[Any]],
) -> CacheState:
    """Try cache; on miss call loader and store. Returns (value, x-cache header)."""
    if cache.backend == "noop":
        value = await loader()
        return value, "BYPASS"
    hit = await cache.get(key)
    if hit is not None:
        return hit, "HIT"
    value = await loader()
    await cache.set(key, value, ttl=ttl)
    return value, "MISS"
