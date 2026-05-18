"""Оркестратор рендера: Semaphore + to_thread обёртки над синхронными draw-функциями."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException

from aquadx.settings import get_settings
from aquadx.utils.logging import get_logger

log = get_logger("aquadx.render")

T = TypeVar("T")

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().render_concurrency)
    return _semaphore


def reset_semaphore() -> None:
    """Используется в тестах для сброса состояния."""
    global _semaphore
    _semaphore = None


async def run_render(draw: Callable[[], bytes]) -> bytes:
    """Запустить sync draw-функцию в thread под Semaphore с backpressure.

    При переполнении (acquire ждёт > settings.render_acquire_timeout_s) кидаем
    HTTP 503 с заголовком Retry-After, чтобы клиент мог повторить.
    """
    settings = get_settings()
    sem = _get_semaphore()
    try:
        async with asyncio.timeout(settings.render_acquire_timeout_s):
            await sem.acquire()
    except TimeoutError as exc:
        log.warning("render_backpressure_503")
        raise HTTPException(
            status_code=503,
            detail="Render queue is full, retry later",
            headers={"Retry-After": str(int(settings.render_acquire_timeout_s) or 1)},
        ) from exc
    try:
        return await asyncio.to_thread(draw)
    finally:
        sem.release()
