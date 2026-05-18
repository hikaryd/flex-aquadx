from __future__ import annotations

import httpx
import pytest
import respx

from aquadx.meta.loader import META_PATH, MusicMetaLoader, jacket_url
from aquadx.models.domain import MusicMeta
from aquadx.settings import Settings


def test_jacket_url_pattern() -> None:
    # Matches AquaNet/src/libs/scoring.ts: padStart(6,'0').substring(2) prefixed with "00"
    assert jacket_url(834, "https://cdn.example") == "https://cdn.example/d/mai2/music/000834.png"
    assert (
        jacket_url(11402, "https://cdn.example/") == "https://cdn.example/d/mai2/music/001402.png"
    )
    assert jacket_url(100, "https://cdn.example") == "https://cdn.example/d/mai2/music/000100.png"


@pytest.mark.asyncio
async def test_loader_fetches_and_parses() -> None:
    s = Settings(aquadx_data_host="https://cdn.example", cache_ttl_meta_seconds=60)
    loader = MusicMetaLoader(s)
    payload = {
        "834": {
            "name": "Oshama Scramble!",
            "artist": "Silentroom",
            "genre": "niconico",
            "bpm": 200.0,
            "notes": [{"lv": "4.0"}, {"lv": "14.7"}],
        },
        "not-an-int": {"name": "ignored"},
    }
    async with httpx.AsyncClient() as http:
        with respx.mock() as r:
            r.get("https://cdn.example" + META_PATH).respond(200, json=payload)
            count = await loader.load(http=http)
    assert count == 1
    item = loader.get(834)
    assert item is not None
    assert item.title == "Oshama Scramble!"
    assert item.jacket == "https://cdn.example/d/mai2/music/000834.png"
    assert item.levels == [4.0, 14.7]


@pytest.mark.asyncio
async def test_loader_ttl_freshness() -> None:
    s = Settings(cache_ttl_meta_seconds=60)
    loader = MusicMetaLoader(s)
    loader.seed({1: MusicMeta(id=1)})
    assert loader._is_fresh() is True
    assert loader.get(1) is not None
    assert loader.get(999) is None


@pytest.mark.asyncio
async def test_loader_negative_backoff_skips_retry_after_failure() -> None:
    """When the CDN is unreachable the loader must not retry every request —
    it should back off for NEGATIVE_BACKOFF_S so player requests stay fast."""
    s = Settings(aquadx_data_host="https://cdn.example", http_timeout_s=0.1)
    loader = MusicMetaLoader(s)

    async with httpx.AsyncClient() as http:
        with respx.mock() as r:
            route = r.get("https://cdn.example" + META_PATH).mock(
                side_effect=httpx.ConnectError("unreachable")
            )
            # First attempt: tries CDN, fails, swallows (via caller's suppress)
            with pytest.raises(httpx.ConnectError):
                await loader.load(http=http)
            assert route.call_count == 1
            # Second attempt within backoff window: must NOT hit the network
            count = await loader.load(http=http)
            assert count == 0
            assert route.call_count == 1  # still one — backoff held


@pytest.mark.asyncio
async def test_loader_force_overrides_backoff() -> None:
    s = Settings(aquadx_data_host="https://cdn.example", http_timeout_s=0.1)
    loader = MusicMetaLoader(s)
    async with httpx.AsyncClient() as http:
        with respx.mock() as r:
            route = r.get("https://cdn.example" + META_PATH).mock(
                side_effect=httpx.ConnectError("unreachable")
            )
            with pytest.raises(httpx.ConnectError):
                await loader.load(http=http)
            with pytest.raises(httpx.ConnectError):
                await loader.load(http=http, force=True)
            assert route.call_count == 2
