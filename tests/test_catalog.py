from __future__ import annotations

from aquadx.meta.loader import get_loader
from aquadx.models.domain import MusicMeta


def seed_catalog() -> None:
    get_loader().seed(
        {
            8: MusicMeta(
                id=8,
                title="True Love Song",
                artist="Kai",
                genre="maimai",
                version="Ver1.00.00",
                jacket="https://cdn.example/8.png",
                levels=[5.0, 7.2, 10.2, 12.4],
            ),
            834: MusicMeta(
                id=834,
                title="Oshama Scramble!",
                artist="t+pazolite",
                genre="niconico",
                version="Ver3.00.00",
                jacket="https://cdn.example/834.png",
                levels=[4.0, 8.0, 12.0, 14.7],
            ),
        }
    )


def test_catalog_search_and_level_sort(client) -> None:  # type: ignore[no-untyped-def]
    seed_catalog()
    response = client.get("/v1/maimai/catalog/tracks?q=osha&sort=level_desc")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == 834
    assert body["data"][0]["max_level"] == 14.7
    assert body["data"][0]["charts"][3]["difficulty"] == "MASTER"


def test_catalog_filters_by_version_and_difficulty(client) -> None:  # type: ignore[no-untyped-def]
    seed_catalog()
    response = client.get(
        "/v1/maimai/catalog/tracks?version=Ver1.00.00&difficulty=MASTER&min_level=12&max_level=13"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["title"] == "True Love Song"


def test_catalog_versions(client) -> None:  # type: ignore[no-untyped-def]
    seed_catalog()
    response = client.get("/v1/maimai/catalog/versions")
    assert response.status_code == 200
    assert response.json()["data"] == ["Ver1.00.00", "Ver3.00.00"]


def test_miniapp_route(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/miniapp/maimai")
    assert response.status_code == 200
    assert "Track Finder" in response.text
