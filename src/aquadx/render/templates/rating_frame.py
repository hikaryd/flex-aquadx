"""Шаблон RatingFrame: best35/best15 grid карточек как PNG 1920×1200."""

from __future__ import annotations

from dataclasses import dataclass

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
    RANK_COLORS,
)

W, H = 1920, 1200


@dataclass(frozen=True)
class RatingItem:
    music_id: int
    title: str
    level: float
    difficulty: str
    achievement: float
    rank: str
    rating_contribution: int


@dataclass(frozen=True)
class RatingFrameInput:
    username: str
    rating: int
    b35_sum: int
    b15_sum: int
    b35: list[RatingItem]
    b15: list[RatingItem]
    jackets_b35: list[skia.Image | None]
    jackets_b15: list[skia.Image | None]
    brand: str = "flex-aquadx"


def _gradient_mesh(canvas: skia.Canvas) -> None:
    paint = skia.Paint(AntiAlias=True)
    paint.setShader(
        skia.GradientShader.MakeLinear(
            points=[skia.Point(0, 0), skia.Point(0, H)],
            colors=[C_BG_TOP, C_BG_BOT],
        )
    )
    canvas.drawRect(skia.Rect.MakeWH(W, H), paint)
    for center, radius, color in (
        (skia.Point(W * 0.10, H * 0.10), W * 0.55, C_MESH_VIOLET),
        (skia.Point(W * 0.90, H * 0.10), W * 0.50, C_MESH_CYAN),
        (skia.Point(W * 0.50, H * 0.95), W * 0.60, C_MESH_PINK),
    ):
        p = skia.Paint(AntiAlias=True)
        p.setShader(
            skia.GradientShader.MakeRadial(
                center=center,
                radius=radius,
                colors=[color, skia.Color4f(color.fR, color.fG, color.fB, 0.0)],
            )
        )
        p.setBlendMode(skia.BlendMode.kPlus)
        canvas.drawRect(skia.Rect.MakeWH(W, H), p)


def _glass(canvas: skia.Canvas, rect: skia.Rect, radius: float = 18.0) -> None:
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
    w = font.measureText(s)
    canvas.drawString(s, right_x - w, y, font, skia.Paint(AntiAlias=True, Color4f=color))


def _ellipsized(font: skia.Font, s: str, max_w: float) -> str:
    if font.measureText(s) <= max_w:
        return s
    ell = "…"
    ew = font.measureText(ell)
    out = ""
    for ch in s:
        if font.measureText(out + ch) + ew > max_w:
            break
        out += ch
    return out + ell


def _jacket(canvas: skia.Canvas, image: skia.Image | None, x: float, y: float, size: float) -> None:
    rect = skia.Rect.MakeXYWH(x, y, size, size)
    canvas.save()
    canvas.clipRRect(skia.RRect.MakeRectXY(rect, 10, 10), True)
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


def _pill(
    canvas: skia.Canvas,
    x: float,
    y: float,
    label: str,
    bg: skia.Color4f,
    *,
    fg: skia.Color4f = skia.Color4f(0.05, 0.02, 0.10, 1.0),
    size: float = 14.0,
    pad_x: float = 10.0,
    pad_y: float = 4.0,
) -> float:
    font = skia.Font(fonts.get("ui-bold"), size)
    text_w = float(font.measureText(label))
    h = size + pad_y * 2
    w = text_w + pad_x * 2
    canvas.drawRoundRect(
        skia.Rect.MakeXYWH(x, y, w, h),
        h / 2,
        h / 2,
        skia.Paint(AntiAlias=True, Color4f=bg),
    )
    canvas.drawString(
        label,
        x + pad_x,
        y + size + pad_y - 3,
        font,
        skia.Paint(AntiAlias=True, Color4f=fg),
    )
    return w


CARD_W = 326.0
CARD_H = 86.0


def _draw_card(
    canvas: skia.Canvas, x: float, y: float, item: RatingItem, image: skia.Image | None, idx: int
) -> None:
    _glass(canvas, skia.Rect.MakeXYWH(x, y, CARD_W, CARD_H), radius=12)
    # Jacket.
    _jacket(canvas, image, x + 8, y + 8, 70.0)

    # Текстовая зона.
    tx = x + 88
    title_font = skia.Font(fonts.get("cjk-bold"), 17)
    title = _ellipsized(title_font, item.title or f"#{item.music_id}", CARD_W - 95 - 50)
    canvas.drawString(title, tx, y + 22, title_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI))

    # Pills row: difficulty + LV.
    pill_y = y + 30
    diff_color = DIFFICULTY_COLORS.get(item.difficulty, DIFFICULTY_COLORS["MASTER"])
    diff_short = item.difficulty if item.difficulty != "RE:MASTER" else "Re:M"
    w1 = _pill(canvas, tx, pill_y, diff_short, diff_color, size=11, pad_x=7, pad_y=3)
    _pill(
        canvas,
        tx + w1 + 5,
        pill_y,
        f"LV {item.level:g}",
        skia.Color4f(0.20, 0.55, 1.0, 0.85),
        size=11,
        pad_x=7,
        pad_y=3,
    )

    # Achievement big.
    ach_font = skia.Font(fonts.get("display"), 24)
    canvas.drawString(
        f"{item.achievement:.4f}%",
        tx,
        y + 76,
        ach_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
    )

    # Rank pill справа.
    rank_color = RANK_COLORS.get(item.rank, skia.Color4f(0.50, 0.50, 0.70, 1.0))
    rank_font = skia.Font(fonts.get("ui-bold"), 14)
    rw = rank_font.measureText(item.rank) + 18
    rank_rect = skia.Rect.MakeXYWH(x + CARD_W - rw - 10, y + 10, rw, 22)
    canvas.drawRoundRect(rank_rect, 11, 11, skia.Paint(AntiAlias=True, Color4f=rank_color))
    canvas.drawString(
        item.rank,
        rank_rect.left() + 9,
        rank_rect.top() + 16,
        rank_font,
        skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.05, 0.02, 0.10, 1.0)),
    )

    # Rating contribution.
    contrib_font = skia.Font(fonts.get("mono-bold"), 16)
    contrib_text = f"→ {item.rating_contribution}"
    cw = contrib_font.measureText(contrib_text)
    canvas.drawString(
        contrib_text,
        x + CARD_W - cw - 10,
        y + 76,
        contrib_font,
        skia.Paint(AntiAlias=True, Color4f=C_ACH_A),
    )

    # Index в углу.
    idx_font = skia.Font(fonts.get("mono"), 11)
    idx_text = f"#{idx:02d}"
    canvas.drawString(
        idx_text,
        x + CARD_W - idx_font.measureText(idx_text) - 10,
        y + 42,
        idx_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT),
    )


def render(inp: RatingFrameInput) -> bytes:
    fonts.preload()
    surface = skia.Surface(W, H)
    with surface as canvas:
        _gradient_mesh(canvas)

        # Hero (слева).
        _glass(canvas, skia.Rect.MakeXYWH(40, 40, 460, 1120))
        _text(canvas, inp.username, 70, 110, 60, role="display")
        _text(canvas, "RATING", 70, 160, 22, color=C_TEXT_FAINT)
        font_big = skia.Font(fonts.get("display"), 96)
        paint_big = skia.Paint(AntiAlias=True)
        paint_big.setShader(
            skia.GradientShader.MakeLinear(
                points=[skia.Point(70, 170), skia.Point(70 + 380, 250)],
                colors=[C_ACH_A, C_ACH_B],
            )
        )
        canvas.drawString(str(inp.rating), 70, 250, font_big, paint_big)

        # Pill «B35 + B15».
        _glass(canvas, skia.Rect.MakeXYWH(70, 280, 400, 90), radius=14)
        _text(canvas, "B35", 90, 320, 22, color=C_TEXT_DIM)
        _text(canvas, f"{inp.b35_sum}", 90, 358, 32, color=C_TEXT_HI, role="display")
        _text(canvas, "B15", 250, 320, 22, color=C_TEXT_DIM)
        _text(canvas, f"{inp.b15_sum}", 250, 358, 32, color=C_TEXT_HI, role="display")

        _text(canvas, "B35 + B15", 70, 410, 22, color=C_TEXT_FAINT)
        _text(
            canvas,
            f"{inp.b35_sum + inp.b15_sum}",
            70,
            454,
            44,
            color=C_ACH_A,
            role="display",
        )

        # Brand под hero.
        _text(canvas, inp.brand, 70, H - 80, 22, color=C_ACH_A, role="ui-bold")
        _text(canvas, "best35 + best15", 70, H - 56, 18, color=C_TEXT_FAINT)

        # Grid B35 — 5 столбцов × 7 строк, начиная с (540, 40).
        grid_x, grid_y = 540, 40
        gap = 12
        _text(canvas, "B35", grid_x, grid_y + 22, 22, color=C_TEXT_DIM)
        _text_right(
            canvas,
            f"35 карт · сумма {inp.b35_sum}",
            W - 40,
            grid_y + 22,
            18,
            color=C_TEXT_FAINT,
        )
        y0 = grid_y + 38
        for i, (item, image) in enumerate(zip(inp.b35, inp.jackets_b35, strict=False)):
            col = i % 5
            row = i // 5
            x = grid_x + col * (CARD_W + gap)
            y = y0 + row * (CARD_H + gap)
            _draw_card(canvas, x, y, item, image, i + 1)

        # Grid B15 — ниже, 5 столбцов × 3 строки.
        y_b15 = y0 + 7 * (CARD_H + gap) + 28
        _text(canvas, "B15", grid_x, y_b15, 22, color=C_TEXT_DIM)
        _text_right(
            canvas,
            f"15 карт · сумма {inp.b15_sum}",
            W - 40,
            y_b15,
            18,
            color=C_TEXT_FAINT,
        )
        y_b15_grid = y_b15 + 16
        for i, (item, image) in enumerate(zip(inp.b15, inp.jackets_b15, strict=False)):
            col = i % 5
            row = i // 5
            x = grid_x + col * (CARD_W + gap)
            y = y_b15_grid + row * (CARD_H + gap)
            _draw_card(canvas, x, y, item, image, 35 + i + 1)

    image = surface.makeImageSnapshot()
    return bytes(image.encodeToData(skia.kPNG, 95))
