from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aquadx.api.errors import NotFoundError, UpstreamError, register_exception_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise UpstreamError("oh no", upstream_status=500, details={"why": "test"})

    @app.get("/missing")
    def missing() -> None:
        raise NotFoundError("not here", upstream_status=404)

    return app


def test_envelope_on_upstream_error() -> None:
    with TestClient(_app()) as c:
        r = c.get("/boom")
        assert r.status_code == 502
        body = r.json()
        assert body == {
            "error": {
                "code": "UPSTREAM_ERROR",
                "message": "oh no",
                "upstream_status": 500,
                "details": {"why": "test"},
            }
        }


def test_envelope_on_not_found() -> None:
    with TestClient(_app()) as c:
        r = c.get("/missing")
        assert r.status_code == 404
        body = r.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["upstream_status"] == 404
