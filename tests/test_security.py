"""Regression tests for architect feedback round 1."""

from __future__ import annotations

import respx
from fastapi.testclient import TestClient
from httpx import Response

BASE = "https://aquadx.net/aqua"
MAI2 = "/api/v2/game/mai2"
CARD = "/api/v2/card"


def test_4xx_upstream_body_does_not_leak_into_envelope(client: TestClient) -> None:
    """Upstream 4xx (non-404) bodies must not be propagated to API consumers."""
    sensitive = {"internal_field": "secret", "stacktrace": "boom"}
    with respx.mock(assert_all_called=False) as r:
        r.get(BASE + f"{CARD}/user-games").mock(return_value=Response(400, json=sensitive))
        response = client.get("/v1/players/anyuser")
    body = response.json()
    assert "error" in body
    # details field must be absent — no upstream body leakage
    assert "details" not in body["error"]
    # Raw upstream payload values must not appear anywhere in the response
    text = response.text
    assert "secret" not in text
    assert "stacktrace" not in text


def test_recent_cache_shared_across_distinct_limits(client: TestClient) -> None:
    """Distinct ?limit=N should hit the same cache entry — only one upstream call."""
    payload = [{"id": i, "musicId": 1, "level": 0, "achievement": 1000000} for i in range(20)]
    with respx.mock(assert_all_called=False) as r:
        route = r.get(BASE + f"{MAI2}/recent").mock(return_value=Response(200, json=payload))
        first = client.get("/v1/players/maisan/maimai/recent?limit=5")
        second = client.get("/v1/players/maisan/maimai/recent?limit=10")
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["data"]) == 5
    assert len(second.json()["data"]) == 10
    # Only one upstream call — second served from cache regardless of limit value
    assert route.call_count == 1
    assert second.headers["x-cache"] == "HIT"
