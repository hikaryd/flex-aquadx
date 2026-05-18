from __future__ import annotations

import respx
from fastapi.testclient import TestClient
from httpx import Response

from aquadx.meta.loader import get_loader, reset_loader
from aquadx.models.domain import MusicMeta
from aquadx.settings import reset_settings_cache

CDN = "https://aquadx.net"


def test_jacket_redirect_by_default(client: TestClient) -> None:
    response = client.get("/v1/assets/maimai/music/834/jacket", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == f"{CDN}/d/mai2/music/000834.png"


def test_jacket_format_json(client: TestClient) -> None:
    response = client.get("/v1/assets/maimai/music/834/jacket?format=json")
    assert response.status_code == 200
    assert response.json() == {"url": f"{CDN}/d/mai2/music/000834.png"}


def test_jacket_proxy_streams(client: TestClient) -> None:
    target = f"{CDN}/d/mai2/music/000834.png"
    with respx.mock(assert_all_called=False) as r:
        r.get(target).mock(
            return_value=Response(200, content=b"PNGBYTES", headers={"content-type": "image/png"})
        )
        response = client.get("/v1/assets/maimai/music/834/jacket?proxy=true")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"PNGBYTES"


def test_jacket_proxy_404_when_cdn_404(client: TestClient) -> None:
    target = f"{CDN}/d/mai2/music/000834.png"
    with respx.mock(assert_all_called=False) as r:
        r.get(target).mock(return_value=Response(404))
        response = client.get("/v1/assets/maimai/music/834/jacket?proxy=true")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_item_icon_redirect(client: TestClient) -> None:
    response = client.get("/v1/assets/maimai/items/plate/42", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == f"{CDN}/d/mai2/plate/000042.png"


def test_item_icon_sanitises_kind(client: TestClient) -> None:
    response = client.get("/v1/assets/maimai/items/bad..kind/1", follow_redirects=False)
    assert response.status_code == 302
    # dots stripped → "badkind"
    assert "/d/mai2/badkind/000001.png" in response.headers["location"]


def test_meta_music_returns_loaded_dictionary(client: TestClient) -> None:
    reset_settings_cache()
    reset_loader()
    get_loader().seed({834: MusicMeta(id=834, title="Oshama Scramble!")})
    response = client.get("/v1/assets/maimai/meta/music")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["count"] == 1
    assert body["data"]["834"]["title"] == "Oshama Scramble!"
    assert body["data"]["834"]["id"] == 834
