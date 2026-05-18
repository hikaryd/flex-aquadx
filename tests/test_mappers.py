from __future__ import annotations

import pytest

from aquadx.mappers.maimai import (
    RANK_THRESHOLDS,
    difficulty_name,
    map_favorites,
    map_profile,
    map_rating_frame,
    map_recent_plays,
    map_trend,
    normalize_achievement,
    parse_rating_csv,
    rank_label,
)
from aquadx.models.domain import MusicMeta


def test_normalize_achievement_examples() -> None:
    assert normalize_achievement(1015234) == 101.5234
    assert normalize_achievement(1000000) == 100.0
    assert normalize_achievement(0) == 0.0


@pytest.mark.parametrize(
    "pct,expected",
    [
        (101.5, "SSS+"),
        (100.5, "SSS+"),
        (100.0, "SSS"),
        (99.7, "SS+"),
        (99.0, "SS"),
        (98.1, "S+"),
        (97.5, "S"),
        (94.2, "AAA"),
        (90.0, "AA"),
        (85.0, "A"),
        (75.5, "BBB"),
        (70.5, "BB"),
        (65.0, "B"),
        (55.0, "C"),
        (10.0, "D"),
    ],
)
def test_rank_label_thresholds(pct: float, expected: str) -> None:
    assert rank_label(pct) == expected


def test_all_rank_thresholds_covered() -> None:
    # sanity: enum order is monotonically decreasing
    prev = float("inf")
    for threshold, _ in RANK_THRESHOLDS:
        assert threshold < prev
        prev = threshold


def test_difficulty_name() -> None:
    assert difficulty_name(0) == "BASIC"
    assert difficulty_name(3) == "MASTER"
    assert difficulty_name(4) == "RE:MASTER"
    assert difficulty_name(99).startswith("LEVEL_")


def test_parse_rating_csv_handles_extras() -> None:
    blob = "834:3:1010234,1124:2:1005000, ,bad:csv,12:1:not-int"
    parsed = parse_rating_csv(blob)
    assert (834, 3, 1010234) in parsed
    assert (1124, 2, 1005000) in parsed
    assert len(parsed) == 2
    assert parse_rating_csv(None) == []
    assert parse_rating_csv("") == []


def test_map_rating_frame_inlines_music_meta_legacy_3field() -> None:
    """Legacy 3-element format: [musicId, level, achievement]. No rating contribution."""
    raw = {
        "best35": [["834", "3", "1010234"], ["1124", "2", "1005000"]],
        "best15": [["555", "3", "990000"]],
        "musicList": [],
    }
    lookup = {
        834: MusicMeta(id=834, title="Oshama Scramble!", artist="Silentroom"),
        555: MusicMeta(id=555, title="Bad Apple"),
    }
    frame = map_rating_frame(raw, music_lookup=lookup)
    assert len(frame.best35) == 2
    assert frame.best35[0].music is not None
    assert frame.best35[0].music.title == "Oshama Scramble!"
    assert frame.best35[0].achievement == 101.0234
    assert frame.best35[0].rank == "SSS+"
    assert frame.best35[0].rating_contribution is None
    # Unknown music id → music is None but entry preserved
    assert frame.best35[1].music is None
    assert len(frame.best15) == 1
    assert frame.best15[0].rank == "SS"


def test_map_rating_frame_handles_4field_upstream_format() -> None:
    """Current upstream format: [musicId, level, ratingContribution, achievement]."""
    raw = {
        "best35": [
            # PANDORA PARADOXXX, RE:MASTER, contrib 19998, ach 100.8790%
            ["834", "4", "19998", "1008790"],
            # 系ぎて, RE:MASTER, contrib 24004, ach 100.6464%
            ["11663", "4", "24004", "1006464"],
        ],
        "best15": [],
        "musicList": [],
    }
    frame = map_rating_frame(raw, music_lookup={})
    assert len(frame.best35) == 2
    t0 = frame.best35[0]
    assert t0.achievement == 100.879
    assert t0.rank == "SSS+"
    assert t0.rating_contribution == 19998
    assert t0.difficulty == "RE:MASTER"
    t1 = frame.best35[1]
    assert t1.achievement == 100.6464
    assert t1.rating_contribution == 24004


def test_map_recent_plays_normalises_and_limits() -> None:
    # mirrors real upstream wire-format: `playlogId` (camelCase), not `id`.
    rows = [
        {
            "playlogId": 1,
            "trackNo": 1,
            "musicId": 100,
            "level": 3,
            "achievement": 980000,
            "playDate": "2026-05-18",
            "userPlayDate": "2026-05-18 14:25:04",
            "placeName": "Some Arcade",
        },
        {
            "playlogId": 2,
            "trackNo": 2,
            "musicId": 101,
            "level": 2,
            "achievement": 950000,
            "isFullCombo": True,
        },
        {"musicId": "not-int", "level": 0, "achievement": 0},  # filtered
    ]
    lookup = {100: MusicMeta(id=100, title="A")}
    out = map_recent_plays(rows, music_lookup=lookup, limit=10)
    assert len(out) == 2
    assert out[0].music is not None and out[0].music.title == "A"
    assert out[0].rank == "S+"
    assert out[0].track_no == 1
    assert out[0].place_name == "Some Arcade"
    assert out[0].user_play_date == "2026-05-18 14:25:04"
    assert out[0].playlog_id is None  # /recent never exposes global PK
    assert out[1].is_full_combo is True
    assert out[1].track_no == 2
    assert out[1].music is None


def test_map_recent_plays_respects_limit() -> None:
    rows = [{"id": i, "musicId": i, "level": 0, "achievement": 1000000} for i in range(5)]
    assert len(map_recent_plays(rows, music_lookup={}, limit=2)) == 2


def test_map_favorites() -> None:
    rows = [{"musicId": 11, "orderId": 1}, {"music_id": 22, "order_id": 2}, {"foo": 1}]
    out = map_favorites(rows, music_lookup={11: MusicMeta(id=11)})
    assert [f.music_id for f in out] == [11, 22]
    assert out[0].music is not None


def test_map_trend() -> None:
    rows = [
        {"playDate": "2026-05-18", "afterRating": 14500},
        {"date": "2026-05-17", "rating": 14400},
        {"playDate": "missing-rating"},
    ]
    out = map_trend(rows)
    assert len(out) == 2
    assert out[0].rating == 14500


def test_map_profile_merges_summary_and_detail() -> None:
    summary = {
        "name": "MaiSan",
        "rating": 14500,
        "serverRank": 42,
        "accuracy": 98.5,
        "ranks": [{"rank": "SSS", "count": 30}],
    }
    detail = {"iconId": 1, "playerRating": 14500, "classRank": 5}
    profile = map_profile("maisan", summary, detail)
    assert profile.username == "maisan"
    assert profile.name == "MaiSan"
    assert profile.rating == 14500
    assert profile.icon_id == 1
    assert profile.class_rank == 5
    assert profile.ranks[0].count == 30
