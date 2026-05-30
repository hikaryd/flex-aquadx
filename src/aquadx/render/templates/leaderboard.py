"""Leaderboard card: общий рейтинг привязанных Telegram-профилей.

Использует тот же editorial dark / Linear-like визуальный язык, что и
RatingFrame/TrackResult: solid dark background, glass surfaces, один accent.
"""

from __future__ import annotations

from dataclasses import dataclass

import skia

from aquadx.render import fonts
from aquadx.render.palette import (
    C_ACCENT,
    C_BG,
    C_GLASS_BORDER,
    C_SURFACE,
    C_SURFACE_HI,
    C_TEXT_DIM,
    C_TEXT_FAINT,
    C_TEXT_HI,
)

# Telegram-first canvas: меньше бесполезного 16:9-воздуха, крупнее текст.
W, H = 1280, 1600
MARGIN = 32
GUTTER = 14
HERO_H = 150
ROW_H = 118


@dataclass(frozen=True)
class LeaderboardEntry:
    username: str
    rating: int
    rank: int
    b35_sum: int = 0
    b15_sum: int = 0
    best_count: int = 0


@dataclass(frozen=True)
class LeaderboardInput:
    title: str
    entries: list[LeaderboardEntry]
    brand: str = "flex-aquadx"


def _background(canvas: skia.Canvas) -> None:
    canvas.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(AntiAlias=True, Color=C_BG))
    paint = skia.Paint(AntiAlias=True)
    paint.setShader(
        skia.GradientShader.MakeLinear(
            points=[skia.Point(0, 0), skia.Point(0, H)],
            colors=[skia.Color4f(1, 1, 1, 0.0), skia.Color4f(0, 0, 0, 0.25)],
        )
    )
    canvas.drawRect(skia.Rect.MakeWH(W, H), paint)


def _surface(canvas: skia.Canvas, rect: skia.Rect, *, radius: float = 16.0, hi: bool = False) -> None:
    rrect = skia.RRect.MakeRectXY(rect, radius, radius)
    canvas.drawRRect(rrect, skia.Paint(AntiAlias=True, Color4f=C_SURFACE_HI if hi else C_SURFACE))
    canvas.drawRRect(
        rrect,
        skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=1.0, Color4f=C_GLASS_BORDER),
    )


def _text(canvas: skia.Canvas, s: str, x: float, y: float, size: float, *, color: skia.Color4f = C_TEXT_HI, role: str = "ui") -> float:
    font = skia.Font(fonts.get(role), size)
    canvas.drawString(s, x, y, font, skia.Paint(AntiAlias=True, Color4f=color))
    return float(font.measureText(s))


def _text_right(canvas: skia.Canvas, s: str, right_x: float, y: float, size: float, *, color: skia.Color4f = C_TEXT_HI, role: str = "ui") -> None:
    font = skia.Font(fonts.get(role), size)
    canvas.drawString(s, right_x - font.measureText(s), y, font, skia.Paint(AntiAlias=True, Color4f=color))


def _label(canvas: skia.Canvas, s: str, x: float, y: float) -> None:
    _text(canvas, s.upper(), x, y, 10.5, color=C_TEXT_FAINT, role="ui-bold")


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


def _draw_medal(canvas: skia.Canvas, cx: float, cy: float, rank: int) -> None:
    colors = {
        1: skia.Color4f(0.95, 0.82, 0.36, 1.0),
        2: skia.Color4f(0.74, 0.78, 0.86, 1.0),
        3: skia.Color4f(0.82, 0.52, 0.32, 1.0),
    }
    color = colors.get(rank, C_TEXT_FAINT)
    canvas.drawCircle(cx, cy, 30, skia.Paint(AntiAlias=True, Color4f=color))
    _text_right(canvas, str(rank), cx + 11, cy + 11, 30 if rank < 10 else 24, color=C_BG if rank <= 3 else C_TEXT_HI, role="mono-bold")


def _draw_row(canvas: skia.Canvas, item: LeaderboardEntry, x: float, y: float, w: float) -> None:
    is_top = item.rank <= 3
    _surface(canvas, skia.Rect.MakeXYWH(x, y, w, ROW_H), radius=20, hi=is_top)
    _draw_medal(canvas, x + 48, y + ROW_H / 2, item.rank)

    name_font = skia.Font(fonts.get("cjk-bold"), 42)
    name = _ellipsized(name_font, item.username, 620)
    canvas.drawString(name, x + 98, y + 52, name_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI))
    _text(canvas, f"B35 {item.b35_sum}  ·  B15 {item.b15_sum}  ·  {item.best_count} карт", x + 98, y + 88, 22, color=C_TEXT_FAINT, role="mono")

    rating_font = skia.Font(fonts.get("mono-bold"), 56)
    rating = str(item.rating)
    canvas.drawString(rating, x + w - rating_font.measureText(rating) - 38, y + 75, rating_font, skia.Paint(AntiAlias=True, Color4f=C_ACCENT))


def render(inp: LeaderboardInput) -> bytes:
    fonts.preload()
    surface = skia.Surface(W, H)
    with surface as canvas:
        _background(canvas)

        hero_x, hero_y = MARGIN, MARGIN
        hero_w, hero_h = W - 2 * MARGIN, HERO_H
        _surface(canvas, skia.Rect.MakeXYWH(hero_x, hero_y, hero_w, hero_h), radius=20)

        _label(canvas, "MAIMAI LEADERBOARD", hero_x + 28, hero_y + 34)
        title_font = skia.Font(fonts.get("cjk-bold"), 52)
        title = _ellipsized(title_font, inp.title, 720)
        canvas.drawString(title, hero_x + 28, hero_y + 92, title_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI))
        _text(canvas, f"{len(inp.entries)} игроков · сортировка по rating", hero_x + 28, hero_y + 126, 24, color=C_TEXT_FAINT)

        top = inp.entries[0] if inp.entries else None
        _label(canvas, "TOP", hero_x + hero_w - 270, hero_y + 34)
        _text_right(canvas, str(top.rating if top else 0), hero_x + hero_w - 28, hero_y + 95, 58, color=C_ACCENT, role="mono-bold")
        top_name = _ellipsized(skia.Font(fonts.get("cjk-bold"), 24), top.username if top else "—", 260)
        _text_right(canvas, top_name, hero_x + hero_w - 28, hero_y + 128, 24, color=C_TEXT_DIM, role="cjk-bold")

        rows_y = MARGIN + HERO_H + 24
        max_rows = int((H - rows_y - MARGIN) // (ROW_H + GUTTER))
        for i, item in enumerate(inp.entries[:max_rows]):
            _draw_row(canvas, item, MARGIN, rows_y + i * (ROW_H + GUTTER), W - 2 * MARGIN)

        if len(inp.entries) > max_rows:
            _text_right(canvas, f"+{len(inp.entries) - max_rows} скрыто", W - MARGIN, H - 18, 13, color=C_TEXT_FAINT, role="mono")

    image = surface.makeImageSnapshot()
    return bytes(image.encodeToData(skia.kPNG, 95))
