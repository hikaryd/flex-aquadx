"""Шаблон TrackResult: рендерит одиночный maimai-скор как PNG 1920×1080."""

from __future__ import annotations

from dataclasses import dataclass, field

import skia

from aquadx.render import fonts
from aquadx.render.palette import (
    C_ACH_A,
    C_ACH_B,
    C_BG_BOT,
    C_BG_TOP,
    C_GLASS_BORDER,
    C_GLASS_FILL,
    C_GLASS_OVER,
    C_MESH_CYAN,
    C_MESH_PINK,
    C_MESH_VIOLET,
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


# ──────────── вспомогательные draw-функции ────────────


def _gradient_mesh(canvas: skia.Canvas) -> None:
    """Editorial background: solid dark + слабый вертикальный затемняющий vignette.

    Никаких цветных gradient-пятен. Имя функции сохранено для совместимости.
    """
    canvas.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(AntiAlias=True, Color=C_BG_TOP))
    vignette = skia.Paint(AntiAlias=True)
    vignette.setShader(
        skia.GradientShader.MakeLinear(
            points=[skia.Point(0, 0), skia.Point(0, H)],
            colors=[skia.Color4f(1, 1, 1, 0.0), skia.Color4f(0, 0, 0, 0.30)],
        )
    )
    canvas.drawRect(skia.Rect.MakeWH(W, H), vignette)
    _ = (C_BG_BOT, C_MESH_VIOLET, C_MESH_PINK, C_MESH_CYAN)


def _glass(canvas: skia.Canvas, rect: skia.Rect, radius: float = 28.0) -> None:
    rrect = skia.RRect.MakeRectXY(rect, radius, radius)
    canvas.drawRRect(rrect, skia.Paint(AntiAlias=True, Color4f=C_GLASS_FILL))
    canvas.drawRRect(rrect, skia.Paint(AntiAlias=True, Color4f=C_GLASS_OVER))
    canvas.drawRRect(
        rrect,
        skia.Paint(
            AntiAlias=True,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=1.0,
            Color4f=C_GLASS_BORDER,
        ),
    )


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


def _gradient_text(
    canvas: skia.Canvas, s: str, x: float, y: float, size: float, role: str = "display"
) -> float:
    font = skia.Font(fonts.get(role), size)
    width = float(font.measureText(s))
    paint = skia.Paint(AntiAlias=True)
    paint.setShader(
        skia.GradientShader.MakeLinear(
            points=[skia.Point(x, y - size), skia.Point(x + width, y)],
            colors=[C_ACH_A, C_ACH_B],
        )
    )
    canvas.drawString(s, x, y, font, paint)
    return width


def _pill(
    canvas: skia.Canvas,
    x: float,
    y: float,
    label: str,
    bg: skia.Color4f,
    *,
    fg: skia.Color4f = skia.Color4f(0.05, 0.02, 0.10, 1.0),
    size: float = 22.0,
    pad_x: float = 16.0,
    pad_y: float = 8.0,
) -> float:
    font = skia.Font(fonts.get("ui-bold"), size)
    text_w = float(font.measureText(label))
    h = size + pad_y * 2
    w = text_w + pad_x * 2
    canvas.drawRoundRect(
        skia.Rect.MakeXYWH(x, y, w, h), h / 2, h / 2, skia.Paint(AntiAlias=True, Color4f=bg)
    )
    canvas.drawString(
        label, x + pad_x, y + size + pad_y - 4, font, skia.Paint(AntiAlias=True, Color4f=fg)
    )
    return w


def _jacket(canvas: skia.Canvas, image: skia.Image | None, x: float, y: float, size: float) -> None:
    rect = skia.Rect.MakeXYWH(x, y, size, size)
    canvas.save()
    canvas.clipRRect(skia.RRect.MakeRectXY(rect, 18, 18), True)
    if image is None:
        paint = skia.Paint(AntiAlias=True)
        paint.setShader(
            skia.GradientShader.MakeLinear(
                points=[skia.Point(x, y), skia.Point(x + size, y + size)],
                colors=[C_MESH_VIOLET, C_MESH_PINK],
            )
        )
        canvas.drawRect(rect, paint)
    else:
        canvas.drawImageRect(image, rect, skia.SamplingOptions(skia.CubicResampler.Mitchell()))
    canvas.restore()
    # Тонкая внешняя обводка.
    canvas.drawRRect(
        skia.RRect.MakeRectXY(rect, 18, 18),
        skia.Paint(
            AntiAlias=True,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=1.0,
            Color4f=C_GLASS_BORDER,
        ),
    )


def _rank_emblem(
    canvas: skia.Canvas, cx: float, cy: float, label: str, radius: float = 130.0
) -> None:
    # Чистая editorial-эмблема: dark glass круг + 1px бордер + текст.
    canvas.drawCircle(
        cx, cy, radius, skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 0.05))
    )
    canvas.drawCircle(
        cx,
        cy,
        radius,
        skia.Paint(
            AntiAlias=True,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=1.5,
            Color4f=skia.Color4f(1, 1, 1, 0.18),
        ),
    )
    # Внутреннее кольцо как тонкая орбита.
    canvas.drawCircle(
        cx,
        cy,
        radius - 14,
        skia.Paint(
            AntiAlias=True,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=1.0,
            Color4f=skia.Color4f(1, 1, 1, 0.08),
        ),
    )

    # Мелкая uppercase-метка над лейблом.
    sub_font = skia.Font(fonts.get("ui-bold"), 11)
    sub_text = "RANK"
    sw = sub_font.measureText(sub_text)
    canvas.drawString(
        sub_text,
        cx - sw / 2,
        cy - radius * 0.45,
        sub_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT),
    )

    size = 78.0 if len(label) <= 4 else 64.0
    font = skia.Font(fonts.get("display"), size)
    tw = font.measureText(label)
    canvas.drawString(
        label,
        cx - tw / 2,
        cy + size * 0.30,
        font,
        skia.Paint(AntiAlias=True, Color4f=C_ACH_A),
    )


def _bar(canvas: skia.Canvas, x: float, y: float, w: float, h: float, fill: float) -> None:
    bg = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1.0, 1.0, 1.0, 0.07))
    canvas.drawRoundRect(skia.Rect.MakeXYWH(x, y, w, h), h / 2, h / 2, bg)
    fw = max(h, w * max(0.0, min(1.0, fill)))
    fill_paint = skia.Paint(AntiAlias=True)
    fill_paint.setShader(
        skia.GradientShader.MakeLinear(
            points=[skia.Point(x, y), skia.Point(x + w, y)],
            colors=[C_ACH_A, C_ACH_B],
        )
    )
    canvas.drawRoundRect(skia.Rect.MakeXYWH(x, y, fw, h), h / 2, h / 2, fill_paint)


def _judgement_card(
    canvas: skia.Canvas, x: float, y: float, label: str, value: int, color: skia.Color4f
) -> None:
    w, h = 170.0, 130.0
    _glass(canvas, skia.Rect.MakeXYWH(x, y, w, h), radius=22)
    _pill(canvas, x + 14, y + 14, label, color, size=18, pad_x=14, pad_y=6)
    val_font = skia.Font(fonts.get("display"), 56)
    canvas.drawString(
        str(value),
        x + 18,
        y + 108,
        val_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
    )


# ──────────── editorial helpers ────────────


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
        _gradient_mesh(canvas)

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
        # under rank: «+12 RATING» дельта.
        if inp.rating_delta != 0:
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

        # ════ Judgements: 5 cells horizontal table with v-rules ════
        cells_y = section_y + 56
        cells_h = 110.0
        cell_count = max(len(inp.judgements), 1)
        cell_w = (W - 120) / cell_count
        total = sum(v for _, v in inp.judgements) or 1
        for i, (lbl, val) in enumerate(inp.judgements):
            cx = 60 + i * cell_w
            color = JUDGEMENT_COLORS.get(lbl, C_TEXT_FAINT)
            # Vertical rule между ячейками (кроме первой).
            if i > 0:
                _v_rule(canvas, cx, cells_y, cells_y + cells_h, alpha=0.08)
            # Eyebrow label.
            _eyebrow(canvas, lbl, cx + 16, cells_y + 22)
            # Big value.
            val_font = skia.Font(fonts.get("display"), 56)
            canvas.drawString(
                str(val),
                cx + 16,
                cells_y + 80,
                val_font,
                skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
            )
            # Percentage right of value.
            pct = (val / total) * 100
            pct_font = skia.Font(fonts.get("mono"), 12)
            canvas.drawString(
                f"{pct:.1f}%",
                cx + 16,
                cells_y + 100,
                pct_font,
                skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT),
            )
            # 2px accent indicator на цвет judgement — слева от ячейки.
            canvas.drawRect(
                skia.Rect.MakeXYWH(cx + 16, cells_y + 12, 28, 2),
                skia.Paint(AntiAlias=True, Color4f=color),
            )

        # ════ Bottom section: NOTE ACCURACY (left) + STATS (right) ════
        bot_y = cells_y + cells_h + 36
        _rule(canvas, 60, bot_y, W - 60)
        _eyebrow(canvas, "NOTE ACCURACY", 60, bot_y + 26)
        _eyebrow(canvas, "STATS", 1180, bot_y + 26)

        notes_y = bot_y + 50
        # NOTE ACCURACY: компактная таблица label | mini-bar | value.
        for i, (lbl, frac, val) in enumerate(inp.note_accuracy):
            ny = notes_y + i * 30
            canvas.drawString(
                lbl,
                60,
                ny + 14,
                skia.Font(fonts.get("mono"), 13),
                skia.Paint(AntiAlias=True, Color4f=C_TEXT_DIM),
            )
            # mini bar 280px.
            bar_x, bar_w, bar_h = 160, 600, 5
            canvas.drawRect(
                skia.Rect.MakeXYWH(bar_x, ny + 8, bar_w, bar_h),
                skia.Paint(AntiAlias=True, Color4f=skia.Color4f(1, 1, 1, 0.06)),
            )
            canvas.drawRect(
                skia.Rect.MakeXYWH(bar_x, ny + 8, max(0.0, min(1.0, frac)) * bar_w, bar_h),
                skia.Paint(AntiAlias=True, Color4f=C_ACH_A),
            )
            _text_right(canvas, str(val), 60 + 800, ny + 16, 14, color=C_TEXT_HI, role="mono-bold")

        # STATS: справа — три блока в линию.
        stats_x = 1180
        stats_top_y = bot_y + 56
        stats = (
            ("RATING", f"{inp.rating}", C_ACH_A),
            ("MAX COMBO", f"{inp.max_combo}", C_TEXT_HI),
            ("DELUXE", f"{inp.deluxe_score}/{inp.deluxe_max}", C_TEXT_HI),
        )
        for i, (stat_lbl, stat_val, stat_col) in enumerate(stats):
            sy = stats_top_y + i * 60
            _eyebrow(canvas, stat_lbl, stats_x, sy)
            val_font = skia.Font(fonts.get("mono-bold"), 32)
            canvas.drawString(
                stat_val,
                stats_x,
                sy + 36,
                val_font,
                skia.Paint(AntiAlias=True, Color4f=stat_col),
            )

        # FAST/LATE компактный hint справа от STATS.
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
