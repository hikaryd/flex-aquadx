from __future__ import annotations

import respx
from fastapi.testclient import TestClient
from httpx import Response

BASE = "https://aquadx.net/aqua"
MAI2 = "/api/v2/game/mai2"
CARD = "/api/v2/card"


def _ranking_payload() -> list[dict[str, object]]:
    return [
        {
            "rank": i + 1,
            "username": f"u{i}",
            "name": f"User{i}",
            "rating": 15000 - i,
            "lastSeen": "2026-05-18",
            "accuracy": 99.0 - i * 0.1,
            "fullCombo": 100 - i,
            "allPerfect": 10,
        }
        for i in range(5)
    ]


def test_ranking_returns_pagination_envelope(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as r:
        r.get(BASE + f"{MAI2}/ranking").mock(return_value=Response(200, json=_ranking_payload()))
        response = client.get("/v1/maimai/ranking?page=0&size=3")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["page"] == 0
    assert body["data"]["size"] == 3
    assert len(body["data"]["entries"]) == 3
    assert body["data"]["entries"][0]["rank"] == 1


def test_ranking_by_username(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as r:
        r.get(BASE + f"{MAI2}/ranking").mock(return_value=Response(200, json=_ranking_payload()))
        response = client.get("/v1/maimai/ranking/u2")
    assert response.status_code == 200
    assert response.json()["data"]["rank"] == 3


def test_ranking_by_username_not_found(client: TestClient) -> None:
    with respx.mock(assert_all_called=False) as r:
        r.get(BASE + f"{MAI2}/ranking").mock(return_value=Response(200, json=_ranking_payload()))
        response = client.get("/v1/maimai/ranking/ghost")
    assert response.status_code == 404


def test_scores_user_music_from_list(client: TestClient) -> None:
    payload = [
        {"musicId": 1, "level": 0, "achievement": 1000000},
        {"musicId": 2, "level": 1, "achievement": 950000},
    ]
    captured: dict[str, object] = {}

    def _capture(request: object) -> Response:
        import json as _json  # local import to avoid polluting module ns

        captured["url"] = str(request.url)  # type: ignore[attr-defined]
        captured["body"] = _json.loads(request.content)  # type: ignore[attr-defined]
        return Response(200, json=payload)

    with respx.mock(assert_all_called=False) as r:
        r.post(BASE + f"{MAI2}/user-music-from-list").mock(side_effect=_capture)
        response = client.get("/v1/players/maisan/maimai/scores?musicIds=1,2,bogus")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    # Upstream contract: username as query param, body is raw [int, ...]
    assert "username=maisan" in str(captured["url"])
    assert captured["body"] == [1, 2]
