from __future__ import annotations

import asyncio

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from aquadx.api.deps import reset_cache
from aquadx.cache.base import cached_call
from aquadx.cache.memory import NoopCache, TTLCache
from aquadx.meta.loader import get_loader, reset_loader
from aquadx.models.domain import MusicMeta
from aquadx.settings import reset_settings_cache

BASE = "https://aquadx.net/aqua"
MAI2 = "/api/v2/game/mai2"
CARD = "/api/v2/card"


def _seed() -> None:
    reset_settings_cache()
    reset_cache()
    reset_loader()
    get_loader().seed({834: MusicMeta(id=834, title="Oshama Scramble!")})


@pytest.mark.asyncio
async def test_ttl_cache_expires() -> None:
    cache = TTLCache()
    await cache.set("k", "v", ttl=1)
    assert await cache.get("k") == "v"
    # Force expiry by manipulating internal store
    cache._store["k"] = (0.0, "v")
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_cached_call_states() -> None:
    cache = TTLCache()
    calls = 0

    async def loader() -> str:
        nonlocal calls
        calls += 1
        return "value"

    v1, s1 = await cached_call(cache, "k", 60, loader)
    v2, s2 = await cached_call(cache, "k", 60, loader)
    assert (v1, s1) == ("value", "MISS")
    assert (v2, s2) == ("value", "HIT")
    assert calls == 1


@pytest.mark.asyncio
async def test_noop_cache_bypasses() -> None:
    cache = NoopCache()
    calls = 0

    async def loader() -> str:
        nonlocal calls
        calls += 1
        return "value"

    _, s1 = await cached_call(cache, "k", 60, loader)
    _, s2 = await cached_call(cache, "k", 60, loader)
    assert s1 == "BYPASS"
    assert s2 == "BYPASS"
    assert calls == 2


def test_player_endpoint_emits_hit_after_miss(client: TestClient) -> None:
    _seed()
    with respx.mock(assert_all_called=False) as r:
        r.get(BASE + f"{CARD}/user-games").mock(
            return_value=Response(
                200,
                json=[{"game": "mai2", "rating": 14500, "name": "MaiSan"}],
            )
        )
        r.get(BASE + f"{MAI2}/user-summary").mock(
            return_value=Response(200, json={"name": "MaiSan", "rating": 14500, "ranks": []})
        )
        first = client.get("/v1/players/maisan")
        second = client.get("/v1/players/maisan")
    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert first.json()["data"] == second.json()["data"]
    assert second.json()["meta"]["cached"] is True


def test_concurrent_safe() -> None:
    async def runner() -> None:
        cache = TTLCache()
        await asyncio.gather(*[cache.set(f"k{i}", i, ttl=10) for i in range(50)])
        values = await asyncio.gather(*[cache.get(f"k{i}") for i in range(50)])
        assert values == list(range(50))

    asyncio.run(runner())
