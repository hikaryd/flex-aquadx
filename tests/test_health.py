from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_ok(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200


def test_info_contains_upstream_and_license(client: TestClient) -> None:
    r = client.get("/v1/info")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "aquadx-python"
    assert body["upstream"].startswith("http")
    assert "CC-BY-NC-SA" in body["license"]
    assert "version" in body


def test_openapi_docs_available(client: TestClient) -> None:
    r = client.get("/docs")
    assert r.status_code == 200
    r2 = client.get("/openapi.json")
    assert r2.status_code == 200
    assert r2.json()["info"]["title"] == "aquadx-python"
