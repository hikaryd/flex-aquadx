from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from fastapi import Response

from aquadx.models.domain import ResponseEnvelope

T = TypeVar("T")


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    @property
    def backend(self) -> str: ...


CacheState = tuple[Any, str]  # (значение, заголовок x-cache)


async def cached_call(
    cache: Cache,
    key: str,
    ttl: int,
    loader: Callable[[], Awaitable[Any]],
) -> CacheState:
    """Сходить в кэш; при промахе вызвать loader и сохранить. Возвращает (значение, x-cache)."""
    if cache.backend == "noop":
        value = await loader()
        return value, "BYPASS"
    hit = await cache.get(key)
    if hit is not None:
        return hit, "HIT"
    value = await loader()
    await cache.set(key, value, ttl=ttl)
    return value, "MISS"


async def cached_envelope(  # noqa: UP047  # форма с TypeVar нужна для pydantic-generic
    cache: Cache,
    key: str,
    ttl: int,
    loader: Callable[[], Awaitable[T]],
    response: Response,
) -> ResponseEnvelope[T]:
    """Выполнить кэширующий вызов, выставить заголовок x-cache, обернуть в ResponseEnvelope."""
    value, state = await cached_call(cache, key, ttl, loader)
    response.headers["x-cache"] = state
    envelope: ResponseEnvelope[T] = ResponseEnvelope(data=value)
    envelope.meta.cached = state == "HIT"
    return envelope
