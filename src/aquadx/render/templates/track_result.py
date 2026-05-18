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


# ──────────── публичный API ────────────


def render(inp: TrackResultInput) -> bytes:
    fonts.preload()
    surface = skia.Surface(W, H)
    with surface as canvas:
        _gradient_mesh(canvas)

        # Верхняя плашка — заголовок трека.
        _glass(canvas, skia.Rect.MakeXYWH(40, 36, 1300, 240))
        _jacket(canvas, inp.jacket, 70, 66, 180)

        title_x = 280.0
        _text(canvas, inp.title, title_x, 110, 56, role="cjk-bold")
        _text(canvas, inp.artist, title_x, 156, 28, color=C_TEXT_DIM, role="cjk")

        diff_color = DIFFICULTY_COLORS.get(inp.difficulty, DIFFICULTY_COLORS["MASTER"])
        w1 = _pill(canvas, title_x, 184, inp.difficulty, diff_color)
        w2 = _pill(
            canvas,
            title_x + w1 + 12,
            184,
            f"LV {inp.level:g}",
            skia.Color4f(0.20, 0.55, 1.0, 0.85),
        )
        _text(
            canvas,
            inp.chart_tag,
            title_x + w1 + w2 + 36,
            184 + 22 + 8 - 4,
            22,
            color=C_ACH_A,
            role="ui-bold",
        )

        # Правый столбец метрик.
        right_x, right_w = 1380.0, 500.0
        _glass(canvas, skia.Rect.MakeXYWH(right_x, 36, right_w, 96))
        _text(canvas, "RATING", right_x + 28, 80, 22, color=C_TEXT_FAINT)
        _text_right(
            canvas,
            f"{inp.rating}",
            right_x + right_w - 28,
            96,
            48,
            color=C_ACH_A,
            role="display",
        )

        _glass(canvas, skia.Rect.MakeXYWH(right_x, 148, right_w, 88))
        _text(canvas, "RANK", right_x + 28, 192, 22, color=C_TEXT_FAINT)
        _text_right(
            canvas,
            inp.rank,
            right_x + right_w - 28,
            204,
            36,
            color=C_TEXT_HI,
            role="display",
        )

        _glass(canvas, skia.Rect.MakeXYWH(right_x, 252, right_w, 122))
        _text(canvas, "MAX COMBO", right_x + 28, 296, 22, color=C_TEXT_FAINT)
        _text_right(
            canvas,
            f"{inp.max_combo}",
            right_x + right_w - 28,
            316,
            44,
            color=C_ACH_A,
            role="display",
        )
        _text_right(
            canvas,
            f"FAST {inp.fast}  ·  LATE {inp.late}",
            right_x + right_w - 28,
            352,
            22,
            color=C_TEXT_FAINT,
        )

        _glass(canvas, skia.Rect.MakeXYWH(right_x, 388, right_w, 122))
        _text(canvas, "でらっくスコア", right_x + 28, 432, 22, color=C_TEXT_FAINT, role="cjk")
        _text_right(
            canvas,
            f"{inp.deluxe_score}",
            right_x + right_w - 90,
            452,
            44,
            color=skia.Color4f(0.70, 0.55, 1.0, 1.0),
            role="display",
        )
        _text_right(
            canvas,
            f"/{inp.deluxe_max}",
            right_x + right_w - 28,
            452,
            28,
            color=C_TEXT_FAINT,
            role="display",
        )
        sign = "+" if inp.rating_delta >= 0 else ""
        _text_right(
            canvas,
            f"{sign}{inp.rating_delta} rating",
            right_x + right_w - 28,
            490,
            22,
            color=skia.Color4f(1.0, 0.80, 0.30, 1.0),
        )

        # Центральная плашка ACHIEVEMENT.
        _glass(canvas, skia.Rect.MakeXYWH(40, 300, 1300, 440))
        _text(canvas, "ACHIEVEMENT", 90, 354, 26, color=C_TEXT_DIM)
        chip_w = _pill(
            canvas, 600, 332, "TRACK RESULT", skia.Color4f(0.35, 0.18, 0.55, 0.95), size=22
        )
        _ = chip_w

        ach_text = f"{inp.achievement:.4f}"
        ach_w = _gradient_text(canvas, ach_text, 90, 590, 200)
        _text(canvas, "%", 90 + ach_w + 10, 590, 88, color=C_ACH_A, role="display")

        _rank_emblem(canvas, cx=1230, cy=520, label=inp.rank, radius=110)

        # NOTE ACCURACY.
        _glass(canvas, skia.Rect.MakeXYWH(40, 760, 900, 280))
        _text(canvas, "NOTE ACCURACY", 78, 800, 22, color=C_TEXT_FAINT)
        for i, (lbl, frac, val) in enumerate(inp.note_accuracy):
            yy = 836 + i * 40
            _text(canvas, lbl, 78, yy + 22, 20, color=C_TEXT_DIM)
            _bar(canvas, 200, yy + 6, 600, 20, frac)
            _text_right(canvas, str(val), 880, yy + 24, 22, color=C_TEXT_HI, role="mono-bold")

        # JUDGEMENTS.
        _glass(canvas, skia.Rect.MakeXYWH(960, 760, 920, 280))
        _text(canvas, "JUDGEMENTS", 998, 800, 22, color=C_TEXT_FAINT)
        for i, (lbl, val) in enumerate(inp.judgements):
            color = JUDGEMENT_COLORS.get(lbl, skia.Color4f(0.6, 0.6, 0.7, 1.0))
            _judgement_card(canvas, 990 + i * 178, 836, lbl, val, color)

        # Watermark.
        _text(canvas, inp.play_date, 60, 1058, 20, color=C_TEXT_FAINT, role="mono")
        _text_right(canvas, inp.brand, 1860, 1058, 22, color=C_ACH_A, role="ui-bold")

    image = surface.makeImageSnapshot()
    return bytes(image.encodeToData(skia.kPNG, 95))
