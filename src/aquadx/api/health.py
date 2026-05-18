from __future__ import annotations

from fastapi import APIRouter

from aquadx import __version__
from aquadx.settings import Settings, get_settings

router = APIRouter(tags=["meta"])


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/v1/info", summary="Service info")
async def info() -> dict[str, str | None]:
    s: Settings = get_settings()
    return {
        "service": s.service_name,
        "version": __version__,
        "upstream": s.aquadx_base_url,
        "data_host": s.aquadx_data_host,
        "license": "CC-BY-NC-SA-4.0 (inherited from AquaDX)",
    }
