"""Загрузка и кэширование upstream music meta JSON (maimai DX).

CDN upstream отдаёт `/maimai/meta/00/all-music.json`. Получаем лениво
с TTL 24 часа и предоставляем поиск get(music_id) → MusicMeta.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from aquadx.models.domain import MusicMeta
from aquadx.settings import Settings, get_settings
from aquadx.utils.logging import get_logger

log = get_logger("aquadx.meta")

# Путь на DATA_HOST с music meta — сверен с продовым бандлом AquaNet на
# aquadx.net: `${DATA_HOST}/d/mai2/00/all-music.json` (внимание: код игры
# `mai2`, а не `maimai`).
META_PATH = "/d/mai2/00/all-music.json"


def jacket_url(music_id: int, base: str) -> str:
    """Сборка абсолютного URL обложки по паттерну из AquaNet/scoring.ts.

    Паттерн: `${DATA_HOST}/d/mai2/music/00{pad(musicId,6).substring(2)}.png`.
    Внимание: upstream использует код игры `mai2`, а не `maimai`.
    """
    padded = f"{music_id:06d}"
    return f"{base.rstrip('/')}/d/mai2/music/00{padded[2:]}.png"


class MusicMetaLoader:
    # Когда CDN недоступен, мы не хотим, чтобы каждый запрос игрока висел
    # `http_timeout_s` секунд — выдерживаем такой бэкофф между попытками.
    NEGATIVE_BACKOFF_S: float = 60.0

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache: dict[int, MusicMeta] = {}
        self._loaded_at: float = 0.0
        self._last_attempt_at: float = 0.0
        self._lock = asyncio.Lock()

    def ttl_seconds(self) -> int:
        return self.settings.cache_ttl_meta_seconds

    def _is_fresh(self) -> bool:
        return bool(self._cache) and (time.monotonic() - self._loaded_at) < self.ttl_seconds()

    def _in_negative_backoff(self) -> bool:
        if self._last_attempt_at == 0.0 or self._cache:
            return False
        return (time.monotonic() - self._last_attempt_at) < self.NEGATIVE_BACKOFF_S

    async def load(self, *, force: bool = False, http: httpx.AsyncClient | None = None) -> int:
        if not force and self._is_fresh():
            return len(self._cache)
        if not force and self._in_negative_backoff():
            return 0
        async with self._lock:
            if not force and self._is_fresh():
                return len(self._cache)
            if not force and self._in_negative_backoff():
                return 0
            url = self.settings.aquadx_data_host.rstrip("/") + META_PATH
            owns = http is None
            client = http or httpx.AsyncClient(timeout=self.settings.http_timeout_s)
            # Помечаем попытку ДО сетевого вызова: одновременные вызовы в
            # том же окне бэкоффа пропустят запрос, даже если этот упадёт.
            self._last_attempt_at = time.monotonic()
            try:
                response = await client.get(url)
                response.raise_for_status()
                raw = response.json()
            finally:
                if owns:
                    await client.aclose()
            self._cache = _parse_meta(raw, self.settings.aquadx_data_host)
            self._loaded_at = time.monotonic()
            log.info("music_meta_loaded", count=len(self._cache))
        return len(self._cache)

    def get(self, music_id: int) -> MusicMeta | None:
        return self._cache.get(music_id)

    def all(self) -> dict[int, MusicMeta]:
        return dict(self._cache)

    def seed(self, items: dict[int, MusicMeta]) -> None:
        """Для тестов: подкинуть данные без обращения в сеть."""
        self._cache = dict(items)
        self._loaded_at = time.monotonic()


def _str_or_none(v: Any) -> str | None:
    """Приводит значение upstream к str — у некоторых записей name/artist приходят int."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


def _parse_meta(raw: Any, base: str) -> dict[int, MusicMeta]:
    if not isinstance(raw, dict):
        return {}
    out: dict[int, MusicMeta] = {}
    for key, value in raw.items():
        try:
            mid = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        levels: list[float] = []
        for note in value.get("notes") or []:
            if isinstance(note, dict) and "lv" in note:
                try:
                    levels.append(float(note["lv"]))
                except (TypeError, ValueError):
                    continue
        bpm_raw = value.get("bpm")
        bpm: float | None
        if isinstance(bpm_raw, (int, float)):
            bpm = float(bpm_raw)
        else:
            try:
                bpm = float(bpm_raw) if bpm_raw is not None else None
            except (TypeError, ValueError):
                bpm = None
        out[mid] = MusicMeta(
            id=mid,
            title=_str_or_none(value.get("name")),
            artist=_str_or_none(value.get("artist") or value.get("composer")),
            genre=_str_or_none(value.get("genre")),
            bpm=bpm,
            jacket=jacket_url(mid, base),
            levels=levels,
        )
    return out


_loader: MusicMetaLoader | None = None


def get_loader() -> MusicMetaLoader:
    global _loader
    if _loader is None:
        _loader = MusicMetaLoader()
    return _loader


def reset_loader() -> None:
    global _loader
    _loader = None
