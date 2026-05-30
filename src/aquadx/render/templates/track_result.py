"""Шаблон TrackResult: рендерит одиночный maimai-скор как Telegram-first PNG 1280×1600."""

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

# Telegram-first portrait canvas: крупнее на мобильных экранах, чем старый 16:9.
W, H = 1280, 1600


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


def _ellipsized(font: skia.Font, s: str, max_w: float) -> str:
    if font.measureText(s) <= max_w:
        return s
    ell = "…"
    while s and font.measureText(s + ell) > max_w:
        s = s[:-1]
    return s + ell


def _rating_delta_badge(canvas: skia.Canvas, x: float, y: float, delta: int) -> None:
    """Large high-priority rating delta badge for Telegram mobile readability."""
    if delta == 0 or abs(delta) >= 500:
        return
    sign = "+" if delta > 0 else ""
    value = f"{sign}{delta}"
    label = "RATING"
    w, h = 304.0, 96.0
    rect = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 18, 18)
    fill = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.71, 1.0, 0.42, 0.13))
    stroke = skia.Paint(
        AntiAlias=True,
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=1.5,
        Color4f=skia.Color4f(0.71, 1.0, 0.42, 0.38),
    )
    canvas.drawRRect(rect, fill)
    canvas.drawRRect(rect, stroke)
    _eyebrow(canvas, label, x + 22, y + 31, size=13)
    _text(canvas, value, x + 20, y + 78, 50, color=C_ACH_A, role="display")


# ──────────── публичный API ────────────


def render(inp: TrackResultInput) -> bytes:
    fonts.preload()
    surface = skia.Surface(W, H)
    with surface as canvas:
        _background(canvas)

        margin = 48.0
        _eyebrow(canvas, "TRACK RESULT  ·  MAIMAI DX", margin, 56)
        _eyebrow_right(canvas, inp.play_date or "—", W - margin, 56)
        _rule(canvas, margin, 78, W - margin)

        title_font = skia.Font(fonts.get("cjk-bold"), 54)
        title = _ellipsized(title_font, inp.title, W - 2 * margin)
        canvas.drawString(title, margin, 150, title_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI))
        artist_font = skia.Font(fonts.get("cjk"), 24)
        artist = _ellipsized(artist_font, inp.artist, W - 2 * margin)
        canvas.drawString(artist, margin, 188, artist_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_DIM))

        sticker_w = _diff_sticker(canvas, margin, 222, inp.difficulty, inp.level)
        _text(canvas, inp.chart_tag, margin + sticker_w + 18, 250, 18, color=C_ACH_A, role="ui-bold")

        jacket_size = 360.0
        jacket_x = W - margin - jacket_size
        jacket_y = 298.0
        _jacket_hard(canvas, inp.jacket, jacket_x, jacket_y, jacket_size)

        rank_x = margin
        _eyebrow(canvas, "RANK", rank_x, 330)
        rank_font = skia.Font(fonts.get("display"), 118)
        canvas.drawString(inp.rank, rank_x, 448, rank_font, skia.Paint(AntiAlias=True, Color4f=C_ACH_A))
        _rating_delta_badge(canvas, rank_x, 472, inp.rating_delta)

        stats = (
            ("RATING", f"{inp.rating}", C_ACH_A),
            ("MAX COMBO", f"{inp.max_combo}", C_TEXT_HI),
            ("DELUXE", f"{inp.deluxe_score}/{inp.deluxe_max}", C_TEXT_HI),
        )
        stats_y = 606
        for i, (stat_lbl, stat_val, stat_col) in enumerate(stats):
            sx = margin + i * 205
            _eyebrow(canvas, stat_lbl, sx, stats_y)
            _text(canvas, stat_val, sx, stats_y + 40, 32, color=stat_col, role="mono-bold")

        if inp.fast > 0 or inp.late > 0:
            _eyebrow(canvas, "FAST / LATE", margin, 700)
            _text(canvas, f"{inp.fast} · {inp.late}", margin, 744, 34, color=C_TEXT_HI, role="mono-bold")

        _rule(canvas, margin, 780, W - margin)
        _eyebrow(canvas, "ACHIEVEMENT", margin, 824)
        ach_text = f"{inp.achievement:.4f}"
        ach_font = skia.Font(fonts.get("display"), 172)
        canvas.drawString(ach_text, margin - 4, 988, ach_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI))
        pct_x = margin - 4 + ach_font.measureText(ach_text) + 8
        canvas.drawString("%", pct_x, 988, skia.Font(fonts.get("display"), 70), skia.Paint(AntiAlias=True, Color4f=C_ACH_A))

        section_y = 1058
        _rule(canvas, margin, section_y, W - margin)
        _eyebrow(canvas, "JUDGEMENTS", margin, section_y + 36)
        total = sum(v for _, v in inp.judgements)
        cells_y = section_y + 70
        if total > 0:
            cell_count = max(len(inp.judgements), 1)
            cell_w = (W - 2 * margin) / cell_count
            for i, (lbl, val) in enumerate(inp.judgements):
                cx = margin + i * cell_w
                color = JUDGEMENT_COLORS.get(lbl, C_TEXT_FAINT)
                if i > 0:
                    _v_rule(canvas, cx, cells_y, cells_y + 128, alpha=0.08)
                canvas.drawRect(skia.Rect.MakeXYWH(cx + 14, cells_y + 2, 30, 3), skia.Paint(AntiAlias=True, Color4f=color))
                _eyebrow(canvas, lbl, cx + 14, cells_y + 32)
                _text(canvas, str(val), cx + 14, cells_y + 84, 44, color=C_TEXT_HI, role="display")
                _text(canvas, f"{(val / total) * 100:.1f}%", cx + 14, cells_y + 116, 15, color=C_TEXT_FAINT, role="mono")
        else:
            _text(canvas, "Detailed judgement data is not available.", margin, cells_y + 62, 24, color=C_TEXT_FAINT, role="ui")

        bot_y = 1288
        _rule(canvas, margin, bot_y, W - margin)
        _eyebrow(canvas, "NOTE ACCURACY", margin, bot_y + 36)
        notes_y = bot_y + 72
        has_accuracy = any(val > 0 for _, _, val in inp.note_accuracy)
        if has_accuracy:
            for i, (lbl, frac, val) in enumerate(inp.note_accuracy[:5]):
                ny = notes_y + i * 38
                _text(canvas, lbl, margin, ny + 18, 18, color=C_TEXT_DIM, role="mono")
                bar_x, bar_w, bar_h = margin + 120, W - 2 * margin - 230, 8
                canvas.drawRect(skia.Rect.MakeXYWH(bar_x, ny + 9, bar_w, bar_h), skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 0.06)))
                canvas.drawRect(skia.Rect.MakeXYWH(bar_x, ny + 9, max(0.0, min(1.0, frac)) * bar_w, bar_h), skia.Paint(AntiAlias=True, Color4f=C_ACH_A))
                _text_right(canvas, str(val), W - margin, ny + 20, 18, color=C_TEXT_HI, role="mono-bold")
        else:
            _text(canvas, "Detailed note-accuracy data is not available.", margin, notes_y + 30, 24, color=C_TEXT_FAINT, role="ui")

        _rule(canvas, margin, H - 58, W - margin)
        _eyebrow(canvas, inp.brand, margin, H - 34)
        _eyebrow_right(canvas, f"#{inp.rating}  RATING", W - margin, H - 34)

    image = surface.makeImageSnapshot()
    return bytes(image.encodeToData(skia.kPNG, 95))

