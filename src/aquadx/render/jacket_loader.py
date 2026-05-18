"""Загрузка обложек треков из CDN с SSRF-защитой и negative-cache на 404."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import httpx
import skia

from aquadx.cache.base import Cache
from aquadx.render.cache_keys import jacket_404_key
from aquadx.settings import Settings
from aquadx.utils.logging import get_logger

log = get_logger("aquadx.render.jacket")


def _allowed_hosts(settings: Settings) -> set[str]:
    hosts = {urlparse(settings.aquadx_data_host).netloc}
    if settings.aquadx_data_host_fallback:
        hosts.add(urlparse(settings.aquadx_data_host_fallback).netloc)
    return {h for h in hosts if h}


def is_safe_jacket_url(url: str, settings: Settings) -> bool:
    """SSRF guard: scheme=https, exact netloc match, без userinfo."""
    if not url:
        return False
    p = urlparse(url)
    if p.scheme != "https":
        return False
    if p.username or p.password:
        return False
    return p.netloc in _allowed_hosts(settings)


def _decode_image(content: bytes) -> skia.Image | None:
    """bytes → skia.Image через нативный Skia-декодер (PNG/JPEG/WebP)."""
    if not content:
        return None
    data = skia.Data.MakeWithCopy(content)
    return skia.Image.MakeFromEncoded(data)


async def fetch_jacket(
    url: str,
    *,
    settings: Settings,
    cache: Cache,
    client: httpx.AsyncClient | None = None,
) -> skia.Image | None:
    """Скачать jacket с SSRF-проверкой и негативным кэшем 404.

    Downscale делается при рендере через canvas.drawImageRect с sampling.
    Возвращает skia.Image или None если URL небезопасен / 404 / таймаут / ошибка декода.
    """
    if not is_safe_jacket_url(url, settings):
        log.warning("render_ssrf_blocked", url=url)
        return None

    neg = await cache.get(jacket_404_key(url))
    if neg is not None:
        return None

    owns = client is None
    client = client or httpx.AsyncClient(
        timeout=settings.jacket_fetch_timeout_s,
        follow_redirects=False,
    )
    try:
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            log.warning("jacket_fetch_failed", url=url, error=str(exc))
            return None
        if response.status_code == 404:
            await cache.set(jacket_404_key(url), True, ttl=300)
            return None
        if response.status_code >= 400:
            log.warning("jacket_fetch_4xx", url=url, status=response.status_code)
            return None
        return _decode_image(response.content)
    finally:
        if owns:
            await client.aclose()


async def fetch_jackets(
    urls: list[str],
    *,
    settings: Settings,
    cache: Cache,
) -> list[skia.Image | None]:
    """Параллельная загрузка списка URL через один httpx.AsyncClient."""
    async with httpx.AsyncClient(
        timeout=settings.jacket_fetch_timeout_s,
        follow_redirects=False,
    ) as client:
        return list(
            await asyncio.gather(
                *(fetch_jacket(u, settings=settings, cache=cache, client=client) for u in urls)
            )
        )
