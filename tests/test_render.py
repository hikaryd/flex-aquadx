"""Тесты рендера PNG-карточек."""

from __future__ import annotations

from io import BytesIO

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response
from PIL import Image

from aquadx.cache.memory import TTLCache
from aquadx.meta.loader import get_loader, reset_loader
from aquadx.models.domain import MusicMeta
from aquadx.render import renderer
from aquadx.render.cache_keys import compute_etag
from aquadx.render.jacket_loader import is_safe_jacket_url
from aquadx.render.templates.rating_frame import (
    RatingFrameInput,
    RatingItem,
)
from aquadx.render.templates.rating_frame import (
    render as render_rating,
)
from aquadx.render.templates.track_result import TrackResultInput
from aquadx.render.templates.track_result import render as render_track
from aquadx.settings import Settings

BASE = "https://aquadx.net/aqua"
MAI2 = "/api/v2/game/mai2"


def _seed_meta() -> None:
    reset_loader()
    get_loader().seed(
        {
            42: MusicMeta(
                id=42,
                title="Recent Track",
                artist="Composer",
                levels=[2.0, 5.0, 8.0, 13.3, 14.0, 13.0],
                jacket="https://aquadx.net/d/mai2/music/000042.png",
            ),
        }
    )


def test_track_template_renders_valid_png() -> None:
    inp = TrackResultInput(
        title="オペラ！スペースオペラ！",
        artist="ナユタン星人",
        difficulty="MASTER",
        level=13.3,
        chart_tag="SEGM",
        achievement=100.6796,
        rank="SSS+",
        rating=14848,
        max_combo=983,
        fast=7,
        late=5,
        deluxe_score=2711,
        deluxe_max=2711,
        rating_delta=12,
        judgements=[("CRIT", 63), ("PERFECT", 908), ("GREAT", 12), ("GOOD", 0), ("MISS", 0)],
        note_accuracy=[("TAP", 0.96, 679)],
        play_date="2026-05-18 22:52:54",
    )
    png = render_track(inp)
    img = Image.open(BytesIO(png))
    img.verify()
    img2 = Image.open(BytesIO(png))
    assert img2.size == (1920, 1080)
    assert img2.format == "PNG"


def test_rating_template_renders_valid_png() -> None:
    items = [
        RatingItem(
            music_id=i,
            title=f"Track {i}",
            level=13.0 + (i % 10) * 0.1,
            difficulty="MASTER",
            achievement=100.0 + (i % 5) * 0.2,
            rank="SSS",
            rating_contribution=300 - i,
        )
        for i in range(35)
    ]
    items_b15 = [
        RatingItem(
            music_id=1000 + i,
            title=f"B15-{i}",
            level=12.5,
            difficulty="EXPERT",
            achievement=99.9,
            rank="SS+",
            rating_contribution=280 - i,
        )
        for i in range(15)
    ]
    inp = RatingFrameInput(
        username="Hikary",
        rating=14136,
        b35_sum=sum(it.rating_contribution for it in items),
        b15_sum=sum(it.rating_contribution for it in items_b15),
        b35=items,
        b15=items_b15,
        jackets_b35=[None] * 35,
        jackets_b15=[None] * 15,
    )
    png = render_rating(inp)
    img = Image.open(BytesIO(png))
    img.verify()
    img2 = Image.open(BytesIO(png))
    assert img2.size == (1920, 1200)
    assert img2.format == "PNG"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://aquadx.net/d/mai2/music/000042.png", True),
        ("http://aquadx.net/d/mai2/music/000042.png", False),  # not https
        ("https://aquadx.net.evil.com/d/mai2/music/000042.png", False),  # netloc bypass attempt
        ("https://user:pass@aquadx.net/d/mai2/music/000042.png", False),  # userinfo
        ("https://other-host.com/d/mai2/music/000042.png", False),  # unknown host
    ],
)
def test_ssrf_guard_rejects_dangerous_urls(url: str, expected: bool) -> None:
    settings = Settings(aquadx_data_host="https://aquadx.net")
    assert is_safe_jacket_url(url, settings) is expected


def test_etag_is_deterministic() -> None:
    dto = {"a": 1, "b": [1, 2, 3], "c": "тест"}
    etags = {compute_etag("recent/u/0", dto) for _ in range(100)}
    assert len(etags) == 1
    assert len(next(iter(etags))) == 16


def test_etag_changes_when_payload_changes() -> None:
    e1 = compute_etag("recent/u/0", {"a": 1})
    e2 = compute_etag("recent/u/0", {"a": 2})
    assert e1 != e2


def test_recent_card_endpoint_returns_png(client: TestClient) -> None:
    _seed_meta()
    renderer.reset_semaphore()
    with respx.mock(assert_all_called=False) as r:
        r.get(BASE + f"{MAI2}/recent").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": 1,
                        "musicId": 42,
                        "level": 3,
                        "achievement": 1015234,
                        "isFullCombo": True,
                        "playDate": "2026-05-18",
                        "maxCombo": 983,
                    }
                ],
            )
        )
        r.get(BASE + f"{MAI2}/user-summary").mock(
            return_value=Response(200, json={"name": "MaiSan", "rating": 14848, "ranks": []})
        )
        # CDN запрос на jacket — отдадим пустой ответ чтоб не падать.
        r.get("https://aquadx.net/d/mai2/music/000042.png").mock(return_value=Response(404))
        response = client.get("/v1/players/MaiSan/maimai/recent/card.png?index=0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "etag" in {k.lower() for k in response.headers}
    Image.open(BytesIO(response.content)).verify()


def test_recent_card_cache_hit_on_second_call(client: TestClient) -> None:
    _seed_meta()
    renderer.reset_semaphore()
    with respx.mock(assert_all_called=False) as r:
        r.get(BASE + f"{MAI2}/recent").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": 1,
                        "musicId": 42,
                        "level": 3,
                        "achievement": 1015234,
                        "maxCombo": 983,
                    }
                ],
            )
        )
        r.get(BASE + f"{MAI2}/user-summary").mock(
            return_value=Response(200, json={"name": "MaiSan", "rating": 14848, "ranks": []})
        )
        r.get("https://aquadx.net/d/mai2/music/000042.png").mock(return_value=Response(404))
        first = client.get("/v1/players/MaiSan/maimai/recent/card.png?index=0")
        second = client.get("/v1/players/MaiSan/maimai/recent/card.png?index=0")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert first.content == second.content


def test_rating_card_endpoint_returns_png(client: TestClient) -> None:
    _seed_meta()
    renderer.reset_semaphore()
    with respx.mock(assert_all_called=False) as r:
        # 35 + 15 пар [musicId, level, contrib, achievement].
        b35 = [["42", "3", "300", "1015234"] for _ in range(35)]
        b15 = [["42", "3", "280", "1010000"] for _ in range(15)]
        r.get(BASE + f"{MAI2}/user-rating").mock(
            return_value=Response(200, json={"best35": b35, "best15": b15, "musicList": []})
        )
        r.get(BASE + f"{MAI2}/user-summary").mock(
            return_value=Response(200, json={"name": "Hikary", "rating": 14136, "ranks": []})
        )
        r.get("https://aquadx.net/d/mai2/music/000042.png").mock(return_value=Response(404))
        response = client.get("/v1/players/Hikary/maimai/rating/card.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    img = Image.open(BytesIO(response.content))
    img.verify()
    img2 = Image.open(BytesIO(response.content))
    assert img2.size == (1920, 1200)


def test_ttl_cache_supports_bytes() -> None:
    """Существующий TTLCache должен корректно хранить bytes для image-кэша."""
    import asyncio

    cache = TTLCache()
    payload = b"PNGBYTES" * 100

    async def run() -> None:
        await cache.set("image|x|abc", payload, ttl=60)
        got = await cache.get("image|x|abc")
        assert got == payload

    asyncio.run(run())
