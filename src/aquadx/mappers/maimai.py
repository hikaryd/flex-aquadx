"""Мапперы maimai DX: превращают сырые блоки upstream в чистые domain DTO."""

from __future__ import annotations

from typing import Any

from aquadx.models.domain import (
    DIFFICULTY_NAMES,
    Difficulty,
    FavoriteEntry,
    JudgementCounts,
    MaimaiProfile,
    MusicMeta,
    NoteAccuracy,
    NoteTypeStats,
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


# Таблица rating-фактора по тиру достижения (maimai DX Splash+ /
# обратно вычислено по примерам из живого maimaibot).
_RATING_FACTOR_TABLE: tuple[tuple[float, float], ...] = (
    (50.0, 8.0),
    (60.0, 9.6),
    (70.0, 11.2),
    (75.0, 12.0),
    (80.0, 13.6),
    (90.0, 15.2),
    (94.0, 16.8),
    (97.0, 20.0),
    (98.0, 20.3),
    (99.0, 20.8),
    (99.5, 21.1),
    (100.0, 21.6),
    (100.5, 22.4),
)


def compute_rating_contribution(level: float, achievement_pct: float) -> int:
    """Вычислить maimai DX rating contribution из level и achievement %.

    Формула: `floor(level * factor * min(ach, 100.5) / 100)`,
    factor — табличное значение по тиру ach. Не доверяем сырому полю
    upstream — формула надёжнее и совпадает с публичными tracker'ами.
    """
    if achievement_pct < 50 or level <= 0:
        return 0
    ach = min(achievement_pct, 100.5)
    factor = _RATING_FACTOR_TABLE[0][1]
    for threshold, f in _RATING_FACTOR_TABLE:
        if ach >= threshold:
            factor = f
        else:
            break
    return int(level * factor * ach / 100)


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
    # Реальный rating contribution считаем формулой через chart-уровень
    # (плавающее значение из music meta при наличии). Сырое поле upstream
    # игнорируем — оно может быть deluxe_score / unrelated id / в формате *100.
    chart_lv: float = float(level)
    if music is not None and music.levels:
        idx = level if 0 <= level < len(music.levels) else 0
        if music.levels[idx] > 0:
            chart_lv = float(music.levels[idx])
    computed = compute_rating_contribution(chart_lv, pct) or rating_contribution
    return RatedTrack(
        music=music,
        difficulty=difficulty_name(level),
        achievement=pct,
        rank=rank_label(pct),
        deluxe_score=deluxe_score,
        rating_contribution=computed,
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


def _note_stats(raw: dict[str, Any], prefix: str) -> NoteTypeStats:
    """Извлечь breakdown CRIT/PERFECT/... для одного типа нот (tap/hold/...)."""
    return NoteTypeStats(
        crit=maybe_int(raw.get(f"{prefix}CriticalPerfect")) or 0,
        perfect=maybe_int(raw.get(f"{prefix}Perfect")) or 0,
        great=maybe_int(raw.get(f"{prefix}Great")) or 0,
        good=maybe_int(raw.get(f"{prefix}Good")) or 0,
        miss=maybe_int(raw.get(f"{prefix}Miss")) or 0,
    )


def _judgements(raw: dict[str, Any]) -> JudgementCounts | None:
    """Aggregated CRIT/PERFECT/GREAT/GOOD/MISS поверх всех типов нот."""
    crit = maybe_int(
        raw.get("judgeCriticalPerfect") or raw.get("criticalPerfect") or raw.get("judgeCritical")
    )
    perfect = maybe_int(raw.get("judgePerfect") or raw.get("perfect"))
    great = maybe_int(raw.get("judgeGreat") or raw.get("great"))
    good = maybe_int(raw.get("judgeGood") or raw.get("good"))
    miss = maybe_int(raw.get("judgeMiss") or raw.get("miss"))
    if all(v is None for v in (crit, perfect, great, good, miss)):
        # Aggregate сам из note-type полей если они есть.
        per_type = [_note_stats(raw, p) for p in ("tap", "hold", "slide", "touch", "break")]
        if any(s.total > 0 for s in per_type):
            return JudgementCounts(
                crit=sum(s.crit for s in per_type),
                perfect=sum(s.perfect for s in per_type),
                great=sum(s.great for s in per_type),
                good=sum(s.good for s in per_type),
                miss=sum(s.miss for s in per_type),
            )
        return None
    return JudgementCounts(
        crit=crit or 0,
        perfect=perfect or 0,
        great=great or 0,
        good=good or 0,
        miss=miss or 0,
    )


def _note_accuracy(raw: dict[str, Any]) -> NoteAccuracy | None:
    tap = _note_stats(raw, "tap")
    hold = _note_stats(raw, "hold")
    slide = _note_stats(raw, "slide")
    touch = _note_stats(raw, "touch")
    breaks = _note_stats(raw, "break")
    if any(s.total > 0 for s in (tap, hold, slide, touch, breaks)):
        return NoteAccuracy(tap=tap, hold=hold, slide=slide, touch=touch, **{"break": breaks})
    return None


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
                fast=maybe_int(row.get("judgeFast") or row.get("fastCount")),
                late=maybe_int(row.get("judgeLate") or row.get("lateCount")),
                judgements=_judgements(row),
                note_accuracy=_note_accuracy(row),
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
