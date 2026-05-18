"""Pydantic models describing raw AquaDX upstream shapes.

These mirror the response JSON of /api/v2/* endpoints as closely as is useful.
Fields the upstream uses but we never consume are omitted; extras are tolerated
via model_config so a minor upstream change does not break parsing.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class UpstreamCardSummary(_Loose):
    cardId: str | int | None = None
    extId: int | None = None
    accessTime: str | None = None


class UpstreamGameSummary(_Loose):
    name: str | None = None
    serverRank: int | None = None
    accuracy: float | None = None
    rating: int | None = None
    ratingHighest: int | None = None
    ranks: list[dict[str, Any]] | None = None
    detailedRanks: dict[str, Any] | None = None
    maxCombo: int | None = None
    fullCombo: int | None = None
    allPerfect: int | None = None
    totalPlays: int | None = None


class UpstreamMaiUserRating(_Loose):
    # Each entry is [musicId:str, level:str, achievement:str] (CSV-derived)
    best35: list[list[str]] = Field(default_factory=list)
    best15: list[list[str]] = Field(default_factory=list)
    musicList: list[dict[str, Any]] = Field(default_factory=list)


class UpstreamMaiPlaylog(_Loose):
    id: int | None = None
    musicId: int
    level: int
    achievement: int
    deluxscore: int | None = None
    isFullCombo: bool | None = None
    isAllPerfect: bool | None = None
    isNewRecord: bool | None = None
    maxCombo: int | None = None
    playDate: str | None = None
    afterRating: int | None = None


class UpstreamMaiUserDetail(_Loose):
    userName: str | None = None
    iconId: int | None = None
    plateId: int | None = None
    titleId: int | None = None
    playerRating: int | None = None
    classRank: int | None = None
    courseRank: int | None = None
    lastRomVersion: str | None = None
    lastDataVersion: str | None = None


class UpstreamTrendPoint(_Loose):
    date: str | None = None
    rating: int | None = None


class UpstreamMusicMeta(_Loose):
    name: str | None = None
    composer: str | None = None
    artist: str | None = None
    genre: str | None = None
    bpm: float | None = None
    version: int | None = None
    notes: list[dict[str, Any]] = Field(default_factory=list)
