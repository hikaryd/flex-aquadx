"""«Глазовалка»: пишет poc_track.png и poc_rating.png. Использует финальные шаблоны."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aquadx.render.templates.rating_frame import (  # noqa: E402
    RatingFrameInput,
    RatingItem,
    render as render_rating,
)
from aquadx.render.templates.track_result import (  # noqa: E402
    TrackResultInput,
    render as render_track,
)


def sample_track() -> TrackResultInput:
    return TrackResultInput(
        title="オペラ！スペースオペラ！",
        artist="ナユタン星人",
        difficulty="MASTER",
        level=13.3,
        chart_tag="SEGM",
        achievement=100.6796,
        rank="SSS+",
        rating=14848,
        max_combo=983,
        fast=7,
        late=5,
        deluxe_score=2711,
        deluxe_max=2711,
        rating_delta=12,
        judgements=[("CRIT", 63), ("PERFECT", 908), ("GREAT", 12), ("GOOD", 0), ("MISS", 0)],
        note_accuracy=[
            ("TAP", 0.96, 679),
            ("HOLD", 0.99, 46),
            ("SLIDE", 0.94, 149),
            ("TOUCH", 1.0, 27),
            ("BREAK", 0.92, 82),
        ],
        play_date="2026-05-18 22:52:54",
    )


def _item(
    music_id: int, title: str, lv: float, diff: str, ach: float, rank: str, contrib: int
) -> RatingItem:
    return RatingItem(
        music_id=music_id,
        title=title,
        level=lv,
        difficulty=diff,
        achievement=ach,
        rank=rank,
        rating_contribution=contrib,
    )


def sample_rating() -> RatingFrameInput:
    b35_titles = [
        "Lunatic Vibes",
        "The wheel to the right",
        "OMAKENO Stroke",
        "バベル",
        "Love's Theme of BADASS",
        "ENERGY SYNERGY",
        "氷滅の135小節",
        "エゴロック",
        "FREEDOM DiVE (tpz)",
        "FLUFFY FLASH",
        "きゅうくらりん",
        "Xaleid◆scopiX",
        "Luminaria",
        "M@GICAL☆CURE",
        "エンドマークに希望と涙を",
        "ヒバナ",
        "系ぎて",
        "雨露霜雪",
        "Knight Rider",
        "病み垢ステロイド",
        "Synthesis.",
        "World's end BLACKBOX",
        "R'N'R Monsta",
        "ソリッド",
        "ウミユリ海底譚",
        "オーバーライド",
        "ドーナツホール",
        "MarbleBlue.",
        "Xevel",
        "MYTH Re:LEASE",
        "ラビットホール",
        "folern",
        "ULTRA SYNERGY",
        "Glorious Crown",
        "Azure Vixen",
    ]
    b15_titles = [
        "テトリス",
        "ヒアソビ",
        "Customized Justice",
        "チルノのパーフェクトさん",
        "Let's ミクササイズ",
        "零號車輛",
        "愛♡スクリーム",
        "トレジャーガーデン",
        "殿ッ！？ご乱心！？",
        "テレパシ",
        "ヤミナベ!!!",
        "サイエンス",
        "JINGLE DEATH",
        "みむかわナ…",
        "AiAe",
    ]
    rng_ach = lambda i: 99.0 + (i * 0.0413) % 2.0  # noqa: E731
    rng_contrib = lambda i: 310 - i * 1  # noqa: E731

    b35 = [
        _item(
            1000 + i,
            t,
            13.0 + (i % 12) * 0.1,
            "MASTER" if i % 3 else "RE:MASTER",
            rng_ach(i),
            ["SSS+", "SSS", "SS+", "SS"][i % 4],
            rng_contrib(i),
        )
        for i, t in enumerate(b35_titles)
    ]
    b15 = [
        _item(
            2000 + i,
            t,
            12.5 + (i % 9) * 0.1,
            "MASTER" if i % 4 else "EXPERT",
            rng_ach(i + 35),
            ["SSS+", "SSS", "SS+", "SS", "S+"][i % 5],
            287 - i,
        )
        for i, t in enumerate(b15_titles)
    ]
    return RatingFrameInput(
        username="Hikary",
        rating=14136,
        b35_sum=sum(it.rating_contribution for it in b35),
        b15_sum=sum(it.rating_contribution for it in b15),
        b35=b35,
        b15=b15,
        jackets_b35=[None] * len(b35),
        jackets_b15=[None] * len(b15),
    )


def sample_track_no_data() -> TrackResultInput:
    """Сценарий: upstream /recent не отдаёт judgement/accuracy/fast-late."""
    s = sample_track()
    return TrackResultInput(
        title=s.title,
        artist=s.artist,
        difficulty=s.difficulty,
        level=s.level,
        chart_tag=s.chart_tag,
        achievement=s.achievement,
        rank=s.rank,
        rating=s.rating,
        max_combo=s.max_combo,
        fast=0,
        late=0,
        deluxe_score=s.deluxe_score,
        deluxe_max=s.deluxe_max,
        rating_delta=0,
        judgements=[("CRIT", 0), ("PERFECT", 0), ("GREAT", 0), ("GOOD", 0), ("MISS", 0)],
        note_accuracy=[
            ("TAP", 1.0, 0),
            ("HOLD", 1.0, 0),
            ("SLIDE", 1.0, 0),
            ("TOUCH", 1.0, 0),
            ("BREAK", 1.0, 0),
        ],
        play_date=s.play_date,
    )


if __name__ == "__main__":
    t = ROOT / "poc_track.png"
    r = ROOT / "poc_rating.png"
    t2 = ROOT / "poc_track_nodata.png"
    t.write_bytes(render_track(sample_track()))
    print(f"OK: {t} ({t.stat().st_size // 1024}KB)")
    t2.write_bytes(render_track(sample_track_no_data()))
    print(f"OK: {t2} ({t2.stat().st_size // 1024}KB)")
    r.write_bytes(render_rating(sample_rating()))
    print(f"OK: {r} ({r.stat().st_size // 1024}KB)")
