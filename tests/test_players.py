from __future__ import annotations

from typing import Any

import respx
from fastapi.testclient import TestClient
from httpx import Response

from aquadx.meta.loader import get_loader, reset_loader
from aquadx.models.domain import MusicMeta

BASE = "https://aquadx.net/aqua"
MAI2 = "/api/v2/game/mai2"
CARD = "/api/v2/card"


def _seed_meta() -> None:
    reset_loader()
    get_loader().seed(
        {
            834: MusicMeta(id=834, title="Oshama Scramble!", artist="Silentroom"),
            1124: MusicMeta(id=1124, title="Phony", artist="Tsumiki"),
            42: MusicMeta(id=42, title="Recent Track"),
        }
    )


def _mock(r: respx.Router, path: str, payload: Any, status: int = 200) -> None:
    r.get(BASE + path).mock(return_value=Response(status, json=payload))


def test_player_cross_game(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(
            r,
            f"{CARD}/user-games",
            [{"game": "mai2", "rating": 14500, "name": "MaiSan", "lastPlayDate": "2026-05-18"}],
        )
        _mock(
            r,
            f"{MAI2}/user-summary",
            {
                "name": "MaiSan",
                "rating": 14500,
                "serverRank": 42,
                "accuracy": 98.5,
                "ranks": [{"rank": "SSS", "count": 30}],
            },
        )
        response = client.get("/v1/players/maisan")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["username"] == "maisan"
    assert body["data"]["games"][0]["game"] == "mai2"
    assert body["data"]["maimai"]["rating"] == 14500
    assert "meta" in body


def test_player_not_found(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(r, f"{CARD}/user-games", {"error": "nope"}, status=404)
        response = client.get("/v1/players/ghost")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_maimai_profile(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(
            r,
            f"{MAI2}/user-summary",
            {"name": "MaiSan", "rating": 14500, "ranks": []},
        )
        _mock(
            r,
            f"{MAI2}/user-detail",
            {"userName": "MaiSan", "iconId": 7, "plateId": 1, "classRank": 5},
        )
        response = client.get("/v1/players/maisan/maimai")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["icon_id"] == 7
    assert data["class_rank"] == 5
    assert data["name"] == "MaiSan"


def test_maimai_rating_inlines_music_meta(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(
            r,
            f"{MAI2}/user-rating",
            {
                "best35": [["834", "3", "1010234"], ["1124", "2", "990000"]],
                "best15": [],
                "musicList": [],
            },
        )
        response = client.get("/v1/players/maisan/maimai/rating")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["best35"][0]["music"]["title"] == "Oshama Scramble!"
    assert data["best35"][0]["achievement"] == 101.0234
    assert data["best35"][0]["rank"] == "SSS+"
    assert data["best35"][1]["rank"] == "SS"


def test_maimai_recent_normalises(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(
            r,
            f"{MAI2}/recent",
            [
                {
                    "id": 1,
                    "musicId": 42,
                    "level": 3,
                    "achievement": 980000,
                    "isFullCombo": True,
                    "playDate": "2026-05-18",
                }
            ],
        )
        response = client.get("/v1/players/maisan/maimai/recent?limit=10")
    assert response.status_code == 200
    plays = response.json()["data"]
    assert len(plays) == 1
    assert plays[0]["rank"] == "S+"
    assert plays[0]["is_full_combo"] is True
    assert plays[0]["music"]["title"] == "Recent Track"


def test_maimai_favorites(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(r, f"{MAI2}/user-favorite", [{"musicId": 834, "orderId": 1}])
        response = client.get("/v1/players/maisan/maimai/favorites")
    assert response.status_code == 200
    favs = response.json()["data"]
    assert favs[0]["music_id"] == 834
    assert favs[0]["music"]["title"] == "Oshama Scramble!"


def test_maimai_trend(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(
            r,
            f"{MAI2}/trend",
            [{"playDate": "2026-05-18", "afterRating": 14500}],
        )
        response = client.get("/v1/players/maisan/maimai/trend")
    assert response.status_code == 200
    points = response.json()["data"]
    assert points[0]["rating"] == 14500


def test_recent_validates_limit(client: TestClient) -> None:
    response = client.get("/v1/players/maisan/maimai/recent?limit=999")
    assert response.status_code == 422


def test_rating_404(client: TestClient) -> None:
    _seed_meta()
    with respx.mock(assert_all_called=False) as r:
        _mock(r, f"{MAI2}/user-rating", {"error": "nope"}, status=404)
        response = client.get("/v1/players/ghost/maimai/rating")
    assert response.status_code == 404
