from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AquadxError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        upstream_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.upstream_status = upstream_status
        self.details = details or {}

    def to_envelope(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.upstream_status is not None:
            body["upstream_status"] = self.upstream_status
        if self.details:
            body["details"] = self.details
        return {"error": body}


class NotFoundError(AquadxError):
    code = "NOT_FOUND"
    status_code = 404


class UpstreamError(AquadxError):
    code = "UPSTREAM_ERROR"
    status_code = 502


class UpstreamTimeoutError(UpstreamError):
    code = "UPSTREAM_TIMEOUT"
    status_code = 504


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AquadxError)
    async def aquadx_error_handler(_: Request, exc: AquadxError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_envelope())
