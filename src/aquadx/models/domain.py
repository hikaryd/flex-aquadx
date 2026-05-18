"""Domain DTOs exposed by our /v1/* API. Pydantic v2, immutable where reasonable."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


def _now_utc() -> datetime:
    return datetime.now(UTC)


T = TypeVar("T")

Rank = Literal["SSS+", "SSS", "SS+", "SS", "S+", "S", "AAA", "AA", "A", "BBB", "BB", "B", "C", "D"]

Difficulty = Literal["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER", "UTAGE"]
DIFFICULTY_NAMES: tuple[Difficulty, ...] = (
    "BASIC",
    "ADVANCED",
    "EXPERT",
    "MASTER",
    "RE:MASTER",
    "UTAGE",
)


class Meta(BaseModel):
    cached: bool = False
    fetched_at: datetime = Field(default_factory=_now_utc)
    source: str = "aquadx.net"


class ResponseEnvelope(BaseModel, Generic[T]):  # noqa: UP046  # pydantic v2 generic models
    data: T
    meta: Meta = Field(default_factory=Meta)


class MusicMeta(BaseModel):
    id: int
    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    bpm: float | None = None
    jacket: str | None = None  # URL to /v1/assets/maimai/music/{id}/jacket
    levels: list[float] = Field(default_factory=list)  # per-difficulty constants


class RankCount(BaseModel):
    rank: str
    count: int


class MaimaiProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    username: str
    name: str | None = None
    rating: int | None = None
    rating_highest: int | None = None
    server_rank: int | None = None
    accuracy: float | None = None
    max_combo: int | None = None
    full_combo: int | None = None
    all_perfect: int | None = None
    total_plays: int | None = None
    ranks: list[RankCount] = Field(default_factory=list)
    icon_id: int | None = None
    plate_id: int | None = None
    title_id: int | None = None
    class_rank: int | None = None
    course_rank: int | None = None


class RatedTrack(BaseModel):
    music: MusicMeta | None
    difficulty: Difficulty | str
    achievement: float  # already normalised to % e.g. 101.5234
    rank: Rank | str
    deluxe_score: int | None = None
    rating_contribution: int | None = None


class RatingFrame(BaseModel):
    best35: list[RatedTrack]
    best15: list[RatedTrack]
    total_rating: int | None = None


class RecentPlay(BaseModel):
    playlog_id: int | None = None
    music: MusicMeta | None
    difficulty: Difficulty | str
    achievement: float
    rank: Rank | str
    deluxe_score: int | None = None
    is_full_combo: bool | None = None
    is_all_perfect: bool | None = None
    is_new_record: bool | None = None
    max_combo: int | None = None
    play_date: str | None = None
    after_rating: int | None = None


class FavoriteEntry(BaseModel):
    music_id: int
    music: MusicMeta | None = None
    order_id: int | None = None


class TrendPoint(BaseModel):
    date: str
    rating: int


class GameSummary(BaseModel):
    game: str
    last_seen: str | None = None
    rating: int | None = None
    name: str | None = None


class Player(BaseModel):
    username: str
    games: list[GameSummary] = Field(default_factory=list)
    maimai: MaimaiProfile | None = None


class RankingEntry(BaseModel):
    rank: int
    username: str
    name: str
    rating: int
    last_seen: str | None = None
    accuracy: float | None = None
    full_combo: int | None = None
    all_perfect: int | None = None


class RankingPage(BaseModel):
    page: int
    size: int
    total: int
    entries: list[RankingEntry]


class CardSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    card_id: str | int | None = None
    ext_id: int | None = None
    access_time: str | None = None
    raw: dict[str, Any] | None = None
