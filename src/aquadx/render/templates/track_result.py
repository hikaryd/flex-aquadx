"""Шаблон TrackResult: рендерит одиночный maimai-скор как PNG 1920×1080."""

from __future__ import annotations

from dataclasses import dataclass, field

import skia

from aquadx.render import fonts
from aquadx.render.palette import (
    C_ACH_A,
    C_BG_TOP,
    C_TEXT_DIM,
    C_TEXT_FAINT,
    C_TEXT_HI,
    DIFFICULTY_COLORS,
    JUDGEMENT_COLORS,
)

W, H = 1920, 1080


@dataclass(frozen=True)
class TrackResultInput:
    """Все данные, нужные шаблону. Pure-data — после async-сборки на endpoint."""

    title: str
    artist: str
    difficulty: str  # "MASTER", "RE:MASTER", ...
    level: float  # 13.3
    chart_tag: str  # "SEGM", "ST", "DX" — короткая метка справа от LV
    achievement: float  # 100.6796 (проценты)
    rank: str  # "SSS+"
    rating: int  # 14848
    max_combo: int  # 983
    fast: int  # 7
    late: int  # 5
    deluxe_score: int  # 2711
    deluxe_max: int  # 2711
    rating_delta: int  # +12
    judgements: list[tuple[str, int]] = field(
        default_factory=lambda: [
            ("CRIT", 0),
            ("PERFECT", 0),
            ("GREAT", 0),
            ("GOOD", 0),
            ("MISS", 0),
        ]
    )
    # Список (label, fraction 0..1, value). fraction — для бара, value — справа.
    note_accuracy: list[tuple[str, float, int]] = field(default_factory=list)
    play_date: str = ""  # "2026-05-18 22:52:54"
    jacket: skia.Image | None = None  # уже декодирован
    brand: str = "flex-aquadx"


# ──────────── editorial helpers ────────────


def _background(canvas: skia.Canvas) -> None:
    """Editorial background: solid dark + слабый вертикальный затемняющий vignette."""
    canvas.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(AntiAlias=True, Color=C_BG_TOP))
    vignette = skia.Paint(AntiAlias=True)
    vignette.setShader(
        skia.GradientShader.MakeLinear(
            points=[skia.Point(0, 0), skia.Point(0, H)],
            colors=[skia.Color4f(1, 1, 1, 0.0), skia.Color4f(0, 0, 0, 0.30)],
        )
    )
    canvas.drawRect(skia.Rect.MakeWH(W, H), vignette)


def _text(
    canvas: skia.Canvas,
    s: str,
    x: float,
    y: float,
    size: float,
    *,
    color: skia.Color4f = C_TEXT_HI,
    role: str = "ui-bold",
) -> float:
    font = skia.Font(fonts.get(role), size)
    paint = skia.Paint(AntiAlias=True, Color4f=color)
    canvas.drawString(s, x, y, font, paint)
    return float(font.measureText(s))


def _text_right(
    canvas: skia.Canvas,
    s: str,
    right_x: float,
    y: float,
    size: float,
    *,
    color: skia.Color4f = C_TEXT_HI,
    role: str = "ui-bold",
) -> None:
    font = skia.Font(fonts.get(role), size)
    paint = skia.Paint(AntiAlias=True, Color4f=color)
    w = font.measureText(s)
    canvas.drawString(s, right_x - w, y, font, paint)


def _rule(canvas: skia.Canvas, x1: float, y: float, x2: float, alpha: float = 0.10) -> None:
    """Thin 1px горизонтальная editorial rule line."""
    canvas.drawRect(
        skia.Rect.MakeXYWH(x1, y, x2 - x1, 1),
        skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, alpha)),
    )


def _v_rule(canvas: skia.Canvas, x: float, y1: float, y2: float, alpha: float = 0.08) -> None:
    """Тонкая вертикальная rule line — column gutter."""
    canvas.drawRect(
        skia.Rect.MakeXYWH(x, y1, 1, y2 - y1),
        skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, alpha)),
    )


def _eyebrow(canvas: skia.Canvas, s: str, x: float, y: float, *, size: float = 10.5) -> None:
    """UPPERCASE 10pt лейбл с трекингом, цвет faint — editorial annotation."""
    font = skia.Font(fonts.get("ui-bold"), size)
    canvas.drawString(s.upper(), x, y, font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT))


def _eyebrow_right(
    canvas: skia.Canvas, s: str, right_x: float, y: float, size: float = 10.5
) -> None:
    font = skia.Font(fonts.get("ui-bold"), size)
    w = font.measureText(s.upper())
    canvas.drawString(
        s.upper(), right_x - w, y, font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT)
    )


def _jacket_hard(
    canvas: skia.Canvas, image: skia.Image | None, x: float, y: float, size: float
) -> None:
    """Hard-crop jacket — без радиуса, с тонкой 1px hint-обводкой."""
    rect = skia.Rect.MakeXYWH(x, y, size, size)
    if image is None:
        canvas.drawRect(rect, skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 0.04)))
    else:
        canvas.drawImageRect(image, rect, skia.SamplingOptions(skia.CubicResampler.Mitchell()))
    canvas.drawRect(
        rect,
        skia.Paint(
            AntiAlias=True,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=1.0,
            Color4f=skia.Color4f(1, 1, 1, 0.10),
        ),
    )


def _diff_sticker(canvas: skia.Canvas, x: float, y: float, diff: str, lv: float) -> float:
    """Editorial-sticker: толстый цветной rect + текст внутри. Возвращает ширину."""
    diff_color = DIFFICULTY_COLORS.get(diff, DIFFICULTY_COLORS["MASTER"])
    diff_label = diff.replace("RE:MASTER", "RE:M")
    title_font = skia.Font(fonts.get("display"), 20)
    lv_font = skia.Font(fonts.get("mono-bold"), 14)
    pad = 14.0
    tw = title_font.measureText(diff_label) + 12 + lv_font.measureText(f"LV {lv:g}")
    w = tw + pad * 2
    h = 42.0
    canvas.drawRect(
        skia.Rect.MakeXYWH(x, y, w, h),
        skia.Paint(AntiAlias=True, Color4f=diff_color),
    )
    canvas.drawString(
        diff_label,
        x + pad,
        y + 28,
        title_font,
        skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.05, 0.02, 0.10, 1.0)),
    )
    canvas.drawString(
        f"LV {lv:g}",
        x + pad + title_font.measureText(diff_label) + 12,
        y + 28,
        lv_font,
        skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.05, 0.02, 0.10, 0.85)),
    )
    return float(w)


# ──────────── публичный API ────────────


def render(inp: TrackResultInput) -> bytes:
    fonts.preload()
    surface = skia.Surface(W, H)
    with surface as canvas:
        _background(canvas)

        # ════ Top eyebrow row + rule ════
        _eyebrow(canvas, "TRACK RESULT  ·  MAIMAI DX", 60, 56)
        _eyebrow_right(canvas, inp.play_date or "—", W - 60, 56)
        _rule(canvas, 60, 76, W - 60)

        # ════ Title + Artist + Difficulty sticker (left column, top) ════
        title_y = 130
        title_font_size = 44.0
        # Если title очень длинный — обрежем по ширине 1100.
        title_font = skia.Font(fonts.get("cjk-bold"), title_font_size)
        title_w_max = 1180.0
        title = inp.title
        if title_font.measureText(title) > title_w_max:
            ell = "…"
            while title and title_font.measureText(title + ell) > title_w_max:
                title = title[:-1]
            title = title + ell
        canvas.drawString(
            title, 60, title_y, title_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI)
        )
        _text(canvas, inp.artist, 60, title_y + 32, 22, color=C_TEXT_DIM, role="cjk")

        # Difficulty sticker + chart_tag.
        sticker_y = title_y + 64
        sticker_w = _diff_sticker(canvas, 60, sticker_y, inp.difficulty, inp.level)
        _text(
            canvas,
            inp.chart_tag,
            60 + sticker_w + 16,
            sticker_y + 28,
            16,
            color=C_ACH_A,
            role="ui-bold",
        )

        # ════ Hero ACHIEVEMENT (left side, huge) ════
        ach_text = f"{inp.achievement:.4f}"
        _eyebrow(canvas, "ACHIEVEMENT", 60, 320)
        ach_font = skia.Font(fonts.get("display"), 240)
        canvas.drawString(
            ach_text,
            56,
            548,
            ach_font,
            skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
        )
        ach_w = float(ach_font.measureText(ach_text))
        # «%» сразу за числом, мельче, в accent цвет.
        pct_font = skia.Font(fonts.get("display"), 88)
        canvas.drawString(
            "%",
            56 + ach_w + 8,
            548,
            pct_font,
            skia.Paint(AntiAlias=True, Color4f=C_ACH_A),
        )

        # ════ Right top: Jacket + Rank label ════
        jacket_size = 360.0
        jacket_x = W - 60 - jacket_size
        jacket_y = 110
        _jacket_hard(canvas, inp.jacket, jacket_x, jacket_y, jacket_size)

        # «Rank» eyebrow + большой текст RANK слева от jacket — typography как герой.
        rank_x_right = jacket_x - 32
        _eyebrow_right(canvas, "RANK", rank_x_right, jacket_y + 30)
        rank_font = skia.Font(fonts.get("display"), 96)
        rank_w = rank_font.measureText(inp.rank)
        canvas.drawString(
            inp.rank,
            rank_x_right - rank_w,
            jacket_y + 130,
            rank_font,
            skia.Paint(AntiAlias=True, Color4f=C_ACH_A),
        )
        # under rank: «+N RATING» дельта. Показываем только при разумной дельте.
        # upstream `/recent` иногда отдаёт after_rating как in-session, не профиль —
        # тогда delta = after_rating - profile_rating уходит в большой минус (артефакт).
        if 0 < abs(inp.rating_delta) < 500:
            sign = "+" if inp.rating_delta > 0 else ""
            delta_str = f"{sign}{inp.rating_delta} RATING"
            delta_font = skia.Font(fonts.get("mono-bold"), 18)
            dw = delta_font.measureText(delta_str)
            canvas.drawString(
                delta_str,
                rank_x_right - dw,
                jacket_y + 170,
                delta_font,
                skia.Paint(AntiAlias=True, Color4f=C_ACH_A),
            )

        # ════ Middle rule + section header ════
        section_y = 620
        _rule(canvas, 60, section_y, W - 60)
        _eyebrow(canvas, "JUDGEMENTS", 60, section_y + 26)
        _eyebrow_right(canvas, "BREAKDOWN", W - 60, section_y + 26)

        # ════ Judgements: 5 cells horizontal table ════
        # 2px accent indicator — НАД лейблом (не за ним). Eyebrow ниже.
        total = sum(v for _, v in inp.judgements)
        cells_y = section_y + 56
        cells_h = 110.0
        if total > 0:
            cell_count = max(len(inp.judgements), 1)
            cell_w = (W - 120) / cell_count
            for i, (lbl, val) in enumerate(inp.judgements):
                cx = 60 + i * cell_w
                color = JUDGEMENT_COLORS.get(lbl, C_TEXT_FAINT)
                if i > 0:
                    _v_rule(canvas, cx, cells_y, cells_y + cells_h, alpha=0.08)
                # 2px accent indicator вверху ячейки (над лейблом, не за ним).
                canvas.drawRect(
                    skia.Rect.MakeXYWH(cx + 16, cells_y + 4, 28, 2),
                    skia.Paint(AntiAlias=True, Color4f=color),
                )
                # Eyebrow label чуть ниже indicator.
                _eyebrow(canvas, lbl, cx + 16, cells_y + 26)
                # Big value.
                val_font = skia.Font(fonts.get("display"), 52)
                canvas.drawString(
                    str(val),
                    cx + 16,
                    cells_y + 78,
                    val_font,
                    skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
                )
                # Percentage под value.
                pct = (val / total) * 100
                pct_font = skia.Font(fonts.get("mono"), 12)
                canvas.drawString(
                    f"{pct:.1f}%",
                    cx + 16,
                    cells_y + 98,
                    pct_font,
                    skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT),
                )
        else:
            # Recent endpoint does not expose judgement breakdown. Keep this area clean instead of
            # rendering developer-facing placeholders on user cards.
            _text(
                canvas,
                "Detailed judgement data is not available for this recent score.",
                60,
                cells_y + 60,
                20,
                color=C_TEXT_FAINT,
                role="ui",
            )

        # ════ Bottom section: NOTE ACCURACY (left) + STATS (right) ════
        bot_y = cells_y + cells_h + 36
        _rule(canvas, 60, bot_y, W - 60)
        _eyebrow(canvas, "NOTE ACCURACY", 60, bot_y + 26)
        _eyebrow(canvas, "STATS", 1180, bot_y + 26)

        notes_y = bot_y + 50
        has_accuracy = any(val > 0 for _, _, val in inp.note_accuracy)
        if has_accuracy:
            for i, (lbl, frac, val) in enumerate(inp.note_accuracy):
                ny = notes_y + i * 30
                canvas.drawString(
                    lbl,
                    60,
                    ny + 14,
                    skia.Font(fonts.get("mono"), 13),
                    skia.Paint(AntiAlias=True, Color4f=C_TEXT_DIM),
                )
                bar_x, bar_w, bar_h = 160, 600, 5
                canvas.drawRect(
                    skia.Rect.MakeXYWH(bar_x, ny + 8, bar_w, bar_h),
                    skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 0.06)),
                )
                canvas.drawRect(
                    skia.Rect.MakeXYWH(bar_x, ny + 8, max(0.0, min(1.0, frac)) * bar_w, bar_h),
                    skia.Paint(AntiAlias=True, Color4f=C_ACH_A),
                )
                _text_right(
                    canvas, str(val), 60 + 800, ny + 16, 14, color=C_TEXT_HI, role="mono-bold"
                )
        else:
            _text(
                canvas,
                "Detailed note-accuracy data is not available for this recent score.",
                60,
                notes_y + 22,
                18,
                color=C_TEXT_FAINT,
                role="ui",
            )

        # STATS: справа — три блока в столбик. Stride 56, font 26pt —
        # умещаются все три значения между bot_y и footer-rule (H-50),
        # включая длинное DELUXE «1333/1333».
        stats_x = 1180
        stats_top_y = bot_y + 46
        stats = (
            ("RATING", f"{inp.rating}", C_ACH_A),
            ("MAX COMBO", f"{inp.max_combo}", C_TEXT_HI),
            ("DELUXE", f"{inp.deluxe_score}/{inp.deluxe_max}", C_TEXT_HI),
        )
        for i, (stat_lbl, stat_val, stat_col) in enumerate(stats):
            sy = stats_top_y + i * 56
            _eyebrow(canvas, stat_lbl, stats_x, sy)
            val_font = skia.Font(fonts.get("mono-bold"), 26)
            canvas.drawString(
                stat_val,
                stats_x,
                sy + 30,
                val_font,
                skia.Paint(AntiAlias=True, Color4f=stat_col),
            )

        # FAST/LATE компактный hint справа от STATS — только если есть данные.
        if inp.fast > 0 or inp.late > 0:
            fl_x = 1620
            _eyebrow(canvas, "FAST / LATE", fl_x, stats_top_y)
            fl_font = skia.Font(fonts.get("mono-bold"), 28)
            canvas.drawString(
                f"{inp.fast} · {inp.late}",
                fl_x,
                stats_top_y + 36,
                fl_font,
                skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
            )

        # ════ Footer rule + brand ════
        _rule(canvas, 60, H - 50, W - 60)
        _eyebrow(canvas, inp.brand, 60, H - 28)
        _eyebrow_right(canvas, f"#{inp.rating}  RATING", W - 60, H - 28)

    image = surface.makeImageSnapshot()
    return bytes(image.encodeToData(skia.kPNG, 95))
