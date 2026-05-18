"""Мапперы maimai DX: превращают сырые блоки upstream в чистые domain DTO."""

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

# achievement хранится умноженным на 10000: 101.5234% в UI = 1015234 сырых единиц.
ACHIEVEMENT_SCALE = 10_000.0

# Пороги рангов в сырых единицах (см. AquaDX util.kt mai2Scores).
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


def maybe_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_rating_csv(blob: str | None) -> list[tuple[int, int, int]]:
    """Разбор CSV `recent_rating` / `recent_rating_new` из upstream.

    Формат: `"musicId:level:achievement,..."`.
    Возвращает список (music_id, level, achievement_raw).
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
        mid, lvl, ach = maybe_int(parts[0]), maybe_int(parts[1]), maybe_int(parts[2])
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
    """Маппинг ответа upstream `/game/mai2/user-rating` в чистый RatingFrame.

    Форма upstream: `{"best35": [["mid","lvl","ach"], ...], "best15": [...], "musicList": [...]}`.
    """

    def _from_list(entries: list[list[str]]) -> list[RatedTrack]:
        # Upstream кодирует записи как `[musicId, level, ratingContribution, achievement]`
        # (4 элемента). Legacy/пустые игроки могут отдавать 3-элементные записи —
        # тогда третье значение это achievement, а вклада в рейтинг нет.
        out: list[RatedTrack] = []
        for entry in entries:
            if len(entry) < 3:
                continue
            mid, lvl = maybe_int(entry[0]), maybe_int(entry[1])
            if mid is None or lvl is None:
                continue
            if len(entry) >= 4:
                rating = maybe_int(entry[2])
                achievement = maybe_int(entry[3])
            else:
                rating = None
                achievement = maybe_int(entry[2])
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
        mid = maybe_int(row.get("musicId"))
        if mid is None:
            continue
        ach_raw = maybe_int(row.get("achievement")) or 0
        lvl = maybe_int(row.get("level")) or 0
        pct = normalize_achievement(ach_raw)
        # upstream `/recent` НЕ отдаёт глобальный PK базы данных в JSON
        # (только `playlogId` — внутрисессионный номер трека 1/2/3,
        # который мы кладём в `track_no`). Ключ `id` здесь — настоящий PK,
        # как он отдаётся в admin/write контекстах и тестовых фикстурах:
        # читаем только если он явно присутствует.
        out.append(
            RecentPlay(
                playlog_id=maybe_int(row.get("id")),
                music=music_lookup.get(mid),
                difficulty=difficulty_name(lvl),
                achievement=pct,
                rank=rank_label(pct),
                deluxe_score=maybe_int(
                    row.get("deluxscore") or row.get("deluxScore") or row.get("deluxscoreMax")
                ),
                is_full_combo=row.get("isFullCombo"),
                is_all_perfect=row.get("isAllPerfect"),
                is_new_record=row.get("isNewRecord"),
                max_combo=maybe_int(row.get("maxCombo")),
                play_date=row.get("playDate"),
                user_play_date=row.get("userPlayDate"),
                after_rating=maybe_int(row.get("afterRating")),
                track_no=maybe_int(row.get("trackNo") or row.get("playlogId")),
                place_name=row.get("placeName"),
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
        mid = maybe_int(row.get("musicId") or row.get("music_id"))
        if mid is None:
            continue
        out.append(
            FavoriteEntry(
                music_id=mid,
                music=music_lookup.get(mid),
                order_id=maybe_int(row.get("orderId") or row.get("order_id")),
            )
        )
    return out


def map_trend(rows: list[dict[str, Any]]) -> list[TrendPoint]:
    out: list[TrendPoint] = []
    for row in rows:
        date = row.get("playDate") or row.get("date")
        rating = maybe_int(row.get("afterRating") or row.get("rating"))
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
