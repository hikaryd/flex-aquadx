"""/v1/assets/* — резолвер URL ассетов и (опционально) проксирование jacket/items maimai."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from aquadx.api.deps import get_meta_loader
from aquadx.api.errors import NotFoundError, UpstreamError
from aquadx.meta.loader import MusicMetaLoader, jacket_url
from aquadx.settings import Settings, get_settings

router = APIRouter(prefix="/v1/assets/maimai", tags=["assets"])


def _resolve_item_url(kind: str, item_id: int, settings: Settings) -> str:
    safe_kind = "".join(c for c in kind if c.isalnum() or c in "-_").lower() or "misc"
    return f"{settings.aquadx_data_host.rstrip('/')}/d/mai2/{safe_kind}/{item_id:06d}.png"


async def _proxy(url: str) -> StreamingResponse:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            upstream = await client.get(url)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"CDN unreachable: {url}") from exc
        if upstream.status_code == 404:
            raise NotFoundError(f"Asset not found: {url}", upstream_status=404)
        if upstream.status_code >= 400:
            raise UpstreamError(
                f"CDN error {upstream.status_code}: {url}",
                upstream_status=upstream.status_code,
            )
        content = upstream.content
        media_type = upstream.headers.get("content-type", "application/octet-stream")

    async def _iter() -> AsyncIterator[bytes]:
        yield content

    return StreamingResponse(_iter(), media_type=media_type)


@router.get(
    "/music/{music_id}/jacket",
    summary="Картинка обложки трека (redirect/proxy/json)",
    response_model=None,
)
async def music_jacket(
    music_id: int,
    format: str | None = Query(default=None, pattern="^(json)?$"),
    proxy: bool | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> JSONResponse | RedirectResponse | StreamingResponse:
    url = jacket_url(music_id, settings.aquadx_data_host)
    if format == "json":
        return JSONResponse({"url": url})
    if proxy is True or (proxy is None and settings.assets_mode == "proxy"):
        return await _proxy(url)
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/items/{kind}/{item_id}",
    summary="Иконка предмета (redirect/proxy/json)",
    response_model=None,
)
async def item_icon(
    kind: str,
    item_id: int,
    format: str | None = Query(default=None, pattern="^(json)?$"),
    proxy: bool | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> JSONResponse | RedirectResponse | StreamingResponse:
    url = _resolve_item_url(kind, item_id, settings)
    if format == "json":
        return JSONResponse({"url": url})
    if proxy is True or (proxy is None and settings.assets_mode == "proxy"):
        return await _proxy(url)
    return RedirectResponse(url=url, status_code=302)


@router.get("/meta/music", summary="Полные метаданные музыки (кэш, TTL 24ч)")
async def music_meta_all(
    loader: MusicMetaLoader = Depends(get_meta_loader),
) -> dict[str, object]:
    if not loader.all():
        try:
            await loader.load()
        except Exception as exc:
            raise UpstreamError("Failed to load music meta from CDN") from exc
    return {
        "data": {str(mid): m.model_dump() for mid, m in loader.all().items()},
        "meta": {"count": len(loader.all()), "ttl_seconds": loader.ttl_seconds()},
    }
