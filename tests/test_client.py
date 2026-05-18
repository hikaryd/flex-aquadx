from __future__ import annotations

import httpx
import pytest
import respx

from aquadx.api.errors import NotFoundError, UpstreamError, UpstreamTimeoutError
from aquadx.clients.aquadx import AquadxClient
from aquadx.settings import Settings


@pytest.fixture()
def fast_settings() -> Settings:
    return Settings(http_timeout_s=2.0, http_rps=1000.0)


@pytest.mark.asyncio
async def test_get_returns_json(fast_settings: Settings) -> None:
    async with httpx.AsyncClient(base_url=fast_settings.aquadx_base_url) as inner:
        client = AquadxClient(fast_settings, client=inner)
        with respx.mock(base_url=fast_settings.aquadx_base_url) as r:
            r.get("/api/v2/game/mai2/user-summary").respond(200, json={"name": "X"})
            data = await client.get("/api/v2/game/mai2/user-summary")
            assert data == {"name": "X"}


@pytest.mark.asyncio
async def test_get_404_maps_to_not_found(fast_settings: Settings) -> None:
    async with httpx.AsyncClient(base_url=fast_settings.aquadx_base_url) as inner:
        client = AquadxClient(fast_settings, client=inner)
        with respx.mock(base_url=fast_settings.aquadx_base_url) as r:
            r.get("/api/v2/game/mai2/user-summary").respond(404, json={"error": "nope"})
            with pytest.raises(NotFoundError) as excinfo:
                await client.get("/api/v2/game/mai2/user-summary")
            assert excinfo.value.upstream_status == 404


@pytest.mark.asyncio
async def test_500_retried_three_times_then_upstream_error(fast_settings: Settings) -> None:
    async with httpx.AsyncClient(base_url=fast_settings.aquadx_base_url) as inner:
        client = AquadxClient(fast_settings, client=inner)
        with respx.mock(base_url=fast_settings.aquadx_base_url) as r:
            route = r.get("/api/v2/game/mai2/user-summary").respond(500)
            with pytest.raises(UpstreamError):
                await client.get("/api/v2/game/mai2/user-summary")
            assert route.call_count == 3


@pytest.mark.asyncio
async def test_timeout_maps_to_timeout_error(fast_settings: Settings) -> None:
    async with httpx.AsyncClient(base_url=fast_settings.aquadx_base_url) as inner:
        client = AquadxClient(fast_settings, client=inner)
        with respx.mock(base_url=fast_settings.aquadx_base_url) as r:
            r.get("/api/v2/game/mai2/user-summary").mock(side_effect=httpx.ReadTimeout("slow"))
            with pytest.raises(UpstreamTimeoutError):
                await client.get("/api/v2/game/mai2/user-summary")
