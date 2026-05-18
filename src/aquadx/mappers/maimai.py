"""maimai DX mappers: turn raw upstream blobs into clean domain DTOs."""

from __future__ import annotations

from typing import Any

from aquadx.models.domain import (
    DIFFICULTY_NAMES,
    Difficulty,
    FavoriteEntry,
    MaimaiProfile,
    MusicMeta,
    Rank,
    RankCount,
    RatedTrack,
    RatingFrame,
    RecentPlay,
    TrendPoint,
)

# achievement is stored * 10000. 101.5234% in UI = 1015234 raw.
ACHIEVEMENT_SCALE = 10_000.0

# Rank thresholds in raw units (per AquaDX util.kt mai2Scores)
RANK_THRESHOLDS: tuple[tuple[int, Rank], ...] = (
    (1005000, "SSS+"),
    (1000000, "SSS"),
    (995000, "SS+"),
    (990000, "SS"),
    (980000, "S+"),
    (970000, "S"),
    (940000, "AAA"),
    (900000, "AA"),
    (800000, "A"),
    (750000, "BBB"),
    (700000, "BB"),
    (600000, "B"),
    (500000, "C"),
)


def normalize_achievement(raw: int | float | str) -> float:
    return float(raw) / ACHIEVEMENT_SCALE


def rank_label(achievement_pct: float) -> Rank | str:
    raw = round(achievement_pct * ACHIEVEMENT_SCALE)
    for threshold, label in RANK_THRESHOLDS:
        if raw >= threshold:
            return label
    return "D"


def difficulty_name(level: int) -> Difficulty | str:
    if 0 <= level < len(DIFFICULTY_NAMES):
        return DIFFICULTY_NAMES[level]
    return f"LEVEL_{level}"


def _maybe_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_rating_csv(blob: str | None) -> list[tuple[int, int, int]]:
    """Parse the upstream `recent_rating` / `recent_rating_new` CSV.

    Format: `"musicId:level:achievement,..."`.
    Returns list of (music_id, level, achievement_raw).
    """
    if not blob:
        return []
    out: list[tuple[int, int, int]] = []
    for entry in blob.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) < 3:
            continue
        mid, lvl, ach = _maybe_int(parts[0]), _maybe_int(parts[1]), _maybe_int(parts[2])
        if mid is None or lvl is None or ach is None:
            continue
        out.append((mid, lvl, ach))
    return out


def map_rated_track(
    music_id: int,
    level: int,
    achievement_raw: int,
    *,
    music: MusicMeta | None,
    deluxe_score: int | None = None,
    rating_contribution: int | None = None,
) -> RatedTrack:
    pct = normalize_achievement(achievement_raw)
    return RatedTrack(
        music=music,
        difficulty=difficulty_name(level),
        achievement=pct,
        rank=rank_label(pct),
        deluxe_score=deluxe_score,
        rating_contribution=rating_contribution,
    )


def map_rating_frame(
    raw: dict[str, Any],
    *,
    music_lookup: dict[int, MusicMeta],
) -> RatingFrame:
    """Map the upstream /game/mai2/user-rating response into a clean RatingFrame.

    Upstream shape: `{"best35": [["mid","lvl","ach"], ...], "best15": [...], "musicList": [...]}`.
    """

    def _from_list(entries: list[list[str]]) -> list[RatedTrack]:
        """Upstream encodes entries as `[musicId, level, ratingContribution, achievement]`
        (4 elements). Legacy/empty users may still produce 3-element entries — in that
        case the third value is the achievement and there is no rating contribution.
        """
        out: list[RatedTrack] = []
        for entry in entries:
            if len(entry) < 3:
                continue
            mid, lvl = _maybe_int(entry[0]), _maybe_int(entry[1])
            if mid is None or lvl is None:
                continue
            if len(entry) >= 4:
                rating = _maybe_int(entry[2])
                achievement = _maybe_int(entry[3])
            else:
                rating = None
                achievement = _maybe_int(entry[2])
            if achievement is None:
                continue
            out.append(
                map_rated_track(
                    mid,
                    lvl,
                    achievement,
                    music=music_lookup.get(mid),
                    rating_contribution=rating,
                )
            )
        return out

    best35 = _from_list(raw.get("best35") or [])
    best15 = _from_list(raw.get("best15") or [])
    return RatingFrame(best35=best35, best15=best15, total_rating=None)


def map_recent_plays(
    rows: list[dict[str, Any]],
    *,
    music_lookup: dict[int, MusicMeta],
    limit: int | None = None,
) -> list[RecentPlay]:
    out: list[RecentPlay] = []
    for row in rows:
        data = dict(row)
        mid = _maybe_int(data.get("musicId"))
        if mid is None:
            continue
        ach_raw = _maybe_int(data.get("achievement")) or 0
        lvl = _maybe_int(data.get("level")) or 0
        pct = normalize_achievement(ach_raw)
        # upstream `/recent` does NOT expose the global database PK in its JSON
        # (only `playlogId` which is the 1/2/3 in-session track number). The
        # `id` key here is the real PK used by `/playlog?id=X` and our test
        # fixtures — read it ONLY if explicitly present.
        out.append(
            RecentPlay(
                playlog_id=_maybe_int(data.get("id")),
                music=music_lookup.get(mid),
                difficulty=difficulty_name(lvl),
                achievement=pct,
                rank=rank_label(pct),
                deluxe_score=_maybe_int(
                    data.get("deluxscore") or data.get("deluxScore") or data.get("deluxscoreMax")
                ),
                is_full_combo=data.get("isFullCombo"),
                is_all_perfect=data.get("isAllPerfect"),
                is_new_record=data.get("isNewRecord"),
                max_combo=_maybe_int(data.get("maxCombo")),
                play_date=data.get("playDate"),
                user_play_date=data.get("userPlayDate"),
                after_rating=_maybe_int(data.get("afterRating")),
                track_no=_maybe_int(data.get("trackNo") or data.get("playlogId")),
                place_name=data.get("placeName"),
            )
        )
    if limit is not None:
        return out[:limit]
    return out


def map_favorites(
    rows: list[dict[str, Any]],
    *,
    music_lookup: dict[int, MusicMeta],
) -> list[FavoriteEntry]:
    out: list[FavoriteEntry] = []
    for row in rows:
        mid = _maybe_int(row.get("musicId") or row.get("music_id"))
        if mid is None:
            continue
        out.append(
            FavoriteEntry(
                music_id=mid,
                music=music_lookup.get(mid),
                order_id=_maybe_int(row.get("orderId") or row.get("order_id")),
            )
        )
    return out


def map_trend(rows: list[dict[str, Any]]) -> list[TrendPoint]:
    out: list[TrendPoint] = []
    for row in rows:
        date = row.get("playDate") or row.get("date")
        rating = _maybe_int(row.get("afterRating") or row.get("rating"))
        if not date or rating is None:
            continue
        out.append(TrendPoint(date=str(date), rating=rating))
    return out


def map_profile(
    username: str,
    summary: dict[str, Any],
    detail: dict[str, Any] | None = None,
) -> MaimaiProfile:
    ranks_raw = summary.get("ranks") or []
    ranks = [
        RankCount(rank=str(r.get("rank")), count=int(r.get("count", 0)))
        for r in ranks_raw
        if isinstance(r, dict) and "rank" in r
    ]
    detail = detail or {}
    return MaimaiProfile(
        username=username,
        name=summary.get("name") or detail.get("userName"),
        rating=summary.get("rating") or detail.get("playerRating"),
        rating_highest=summary.get("ratingHighest"),
        server_rank=summary.get("serverRank"),
        accuracy=summary.get("accuracy"),
        max_combo=summary.get("maxCombo"),
        full_combo=summary.get("fullCombo"),
        all_perfect=summary.get("allPerfect"),
        total_plays=summary.get("totalPlays"),
        ranks=ranks,
        icon_id=detail.get("iconId"),
        plate_id=detail.get("plateId"),
        title_id=detail.get("titleId"),
        class_rank=detail.get("classRank"),
        course_rank=detail.get("courseRank"),
    )
