"""/v1/maimai/catalog — быстрый каталог треков для Telegram Mini App."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from aquadx.api.deps import get_meta_loader
from aquadx.api.errors import UpstreamError
from aquadx.meta.loader import MusicMetaLoader
from aquadx.models.domain import DIFFICULTY_NAMES, MusicMeta

router = APIRouter(prefix="/v1/maimai/catalog", tags=["maimai-catalog"])


class ChartSummary(BaseModel):
    difficulty: str
    index: int
    level: float


class CatalogTrack(BaseModel):
    id: int
    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    version: str | None = None
    bpm: float | None = None
    jacket: str | None = None
    levels: list[float] = Field(default_factory=list)
    charts: list[ChartSummary] = Field(default_factory=list)
    max_level: float | None = None
    min_level: float | None = None
    searchable: str


class CatalogResponse(BaseModel):
    data: list[CatalogTrack]
    meta: dict[str, object]


class VersionsResponse(BaseModel):
    data: list[str]
    meta: dict[str, int]


async def _ensure_loaded(loader: MusicMetaLoader) -> None:
    if loader.all():
        return
    try:
        await loader.load()
    except Exception as exc:
        raise UpstreamError("Failed to load maimai music catalog from CDN") from exc


def _track_from_meta(meta: MusicMeta) -> CatalogTrack:
    charts = [
        ChartSummary(difficulty=DIFFICULTY_NAMES[i] if i < len(DIFFICULTY_NAMES) else f"CHART {i + 1}", index=i, level=level)
        for i, level in enumerate(meta.levels)
    ]
    searchable_parts = [
        str(meta.id),
        meta.title or "",
        meta.artist or "",
        meta.genre or "",
        meta.version or "",
    ]
    return CatalogTrack(
        id=meta.id,
        title=meta.title,
        artist=meta.artist,
        genre=meta.genre,
        version=meta.version,
        bpm=meta.bpm,
        jacket=meta.jacket,
        levels=meta.levels,
        charts=charts,
        max_level=max(meta.levels) if meta.levels else None,
        min_level=min(meta.levels) if meta.levels else None,
        searchable=" ".join(searchable_parts).casefold(),
    )


@router.get("/tracks", response_model=CatalogResponse, summary="Поиск и сортировка треков maimai")
async def catalog_tracks(
    q: str = Query(default="", max_length=80),
    version: str | None = Query(default=None, max_length=64),
    difficulty: str | None = Query(default=None, max_length=16),
    min_level: float | None = Query(default=None, ge=1, le=15),
    max_level: float | None = Query(default=None, ge=1, le=15),
    sort: str = Query(default="level_desc", pattern="^(level_desc|level_asc|title|version)$"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    loader: MusicMetaLoader = Depends(get_meta_loader),
) -> CatalogResponse:
    await _ensure_loaded(loader)
    query = q.strip().casefold()
    diff_index = None
    if difficulty:
        normalized = difficulty.strip().upper().replace("REMAS", "RE:MASTER")
        if normalized in DIFFICULTY_NAMES:
            diff_index = DIFFICULTY_NAMES.index(normalized)

    tracks = [_track_from_meta(item) for item in loader.all().values()]
    if query:
        tracks = [track for track in tracks if query in track.searchable]
    if version:
        tracks = [track for track in tracks if track.version == version]
    if diff_index is not None:
        tracks = [track for track in tracks if len(track.levels) > diff_index]
    if min_level is not None:
        if diff_index is None:
            tracks = [track for track in tracks if track.max_level is not None and track.max_level >= min_level]
        else:
            tracks = [track for track in tracks if track.levels[diff_index] >= min_level]
    if max_level is not None:
        if diff_index is None:
            tracks = [track for track in tracks if track.min_level is not None and track.min_level <= max_level]
        else:
            tracks = [track for track in tracks if track.levels[diff_index] <= max_level]

    def level_key(track: CatalogTrack) -> float:
        if diff_index is not None and len(track.levels) > diff_index:
            return track.levels[diff_index]
        return track.max_level or 0.0

    if sort == "level_asc":
        tracks.sort(key=lambda track: (level_key(track), track.title or "", track.id))
    elif sort == "title":
        tracks.sort(key=lambda track: ((track.title or "").casefold(), track.id))
    elif sort == "version":
        tracks.sort(key=lambda track: (track.version or "", -level_key(track), track.title or "", track.id))
    else:
        tracks.sort(key=lambda track: (-level_key(track), track.title or "", track.id))

    total = len(tracks)
    page = tracks[offset : offset + limit]
    return CatalogResponse(data=page, meta={"total": total, "limit": limit, "offset": offset})


@router.get("/versions", response_model=VersionsResponse, summary="Список версий maimai из каталога")
async def catalog_versions(loader: MusicMetaLoader = Depends(get_meta_loader)) -> VersionsResponse:
    await _ensure_loaded(loader)
    versions = sorted({item.version for item in loader.all().values() if item.version})
    return VersionsResponse(data=versions, meta={"count": len(versions)})


def miniapp_index() -> FileResponse:
    return FileResponse(__import__("pathlib").Path(__file__).resolve().parents[2] / "web" / "maimai_catalog.html")
