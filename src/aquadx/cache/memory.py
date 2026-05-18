from __future__ import annotations

import asyncio
import time
from typing import Any


class TTLCache:
    """Async-безопасный in-memory TTL-кэш. TTL на каждый ключ.

    Лёгкий; без LRU-ограничения — подходит для небольшого пространства
    ключей (имена игроков, страницы ранкинга). При росте кардинальности
    подключайте Redis-backend.
    """

    backend = "memory"

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl_s = ttl if ttl is not None and ttl > 0 else 60
        async with self._lock:
            self._store[key] = (time.monotonic() + ttl_s, value)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class NoopCache:
    backend = "noop"

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None
