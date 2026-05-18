"""Шаблон RatingFrame: B35/B15 grid, editorial dark, single accent.

Дизайн: Linear/Vercel-минимализм. Solid dark background, тонкие dark-glass
плитки с 1px бордером 7% alpha, один акцентный цвет (мятно-лайм) только для
ключевых чисел. Никаких градиентных пятен и glow.
"""

from __future__ import annotations

from dataclasses import dataclass

import skia

from aquadx.render import fonts
from aquadx.render.palette import (
    C_ACCENT,
    C_BG,
    C_BG_BOT,
    C_DIVIDER,
    C_GLASS_BORDER,
    C_SURFACE,
    C_SURFACE_HI,
    C_TEXT_DIM,
    C_TEXT_FAINT,
    C_TEXT_HI,
    DIFFICULTY_COLORS,
    RANK_COLORS,
)

# Canvas: 1920×1080 (16:9).
W, H = 1920, 1080

# Поля и сетка.
MARGIN = 40
GUTTER = 12

# Hero (top, full width).
HERO_H = 140

# B35: 7 cols × 5 rows, плотная плитка.
B35_COLS, B35_ROWS = 7, 5
CARD_W_B35 = (W - 2 * MARGIN - (B35_COLS - 1) * GUTTER) / B35_COLS  # 252.57
CARD_H_B35 = 84

# B15: 5 cols × 3 rows, чуть крупнее.
B15_COLS, B15_ROWS = 5, 3
CARD_W_B15 = (W - 2 * MARGIN - (B15_COLS - 1) * GUTTER) / B15_COLS  # 358.40
CARD_H_B15 = 72


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


# ──────────────── низкоуровневые помощники ────────────────


def _background(canvas: skia.Canvas) -> None:
    """Solid фон — без gradient mesh. Очень слабая вертикальная виньетка."""
    canvas.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(AntiAlias=True, Color=C_BG))
    # Тонкий vertical виньет для глубины (НЕ цветной).
    paint = skia.Paint(AntiAlias=True)
    paint.setShader(
        skia.GradientShader.MakeLinear(
            points=[skia.Point(0, 0), skia.Point(0, H)],
            colors=[skia.Color4f(1, 1, 1, 0.0), skia.Color4f(0, 0, 0, 0.25)],
        )
    )
    canvas.drawRect(skia.Rect.MakeWH(W, H), paint)
    _ = C_BG_BOT  # alias оставлен для совместимости импортов


def _surface(canvas: skia.Canvas, rect: skia.Rect, *, radius: float = 16.0) -> None:
    rrect = skia.RRect.MakeRectXY(rect, radius, radius)
    canvas.drawRRect(rrect, skia.Paint(AntiAlias=True, Color4f=C_SURFACE))
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
    role: str = "ui",
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
    role: str = "ui",
) -> None:
    font = skia.Font(fonts.get(role), size)
    w = font.measureText(s)
    canvas.drawString(s, right_x - w, y, font, skia.Paint(AntiAlias=True, Color4f=color))


def _label(canvas: skia.Canvas, s: str, x: float, y: float) -> None:
    """Маленький uppercase-лейбл-«eyebrow», как в Linear UI."""
    font = skia.Font(fonts.get("ui-bold"), 10.5)
    paint = skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT)
    canvas.drawString(s.upper(), x, y, font, paint)


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
    canvas.clipRRect(skia.RRect.MakeRectXY(rect, 8, 8), True)
    if image is None:
        # Плейсхолдер: тёмная solid + тонкая обводка. Без gradient.
        canvas.drawRect(rect, skia.Paint(AntiAlias=True, Color4f=C_SURFACE_HI))
    else:
        canvas.drawImageRect(image, rect, skia.SamplingOptions(skia.CubicResampler.Mitchell()))
    canvas.restore()
    canvas.drawRRect(
        skia.RRect.MakeRectXY(rect, 8, 8),
        skia.Paint(
            AntiAlias=True,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=1.0,
            Color4f=C_GLASS_BORDER,
        ),
    )


def _diff_marker(canvas: skia.Canvas, x: float, y: float, color: skia.Color4f) -> None:
    """4×12 px вертикальная полоска — маркер сложности слева от уровня."""
    canvas.drawRoundRect(
        skia.Rect.MakeXYWH(x, y, 3, 12),
        1.5,
        1.5,
        skia.Paint(AntiAlias=True, Color4f=color),
    )


# ──────────────── карточки рейтинг-фрейма ────────────────


def _draw_card_b35(
    canvas: skia.Canvas, x: float, y: float, item: RatingItem, image: skia.Image | None, idx: int
) -> None:
    _surface(canvas, skia.Rect.MakeXYWH(x, y, CARD_W_B35, CARD_H_B35), radius=12)

    # Jacket 60×60 слева.
    jacket_size = 60.0
    _jacket(canvas, image, x + 12, y + 12, jacket_size)

    # Текстовая колонка.
    tx = x + 12 + jacket_size + 12  # = x + 84
    inner_w = CARD_W_B35 - (tx - x) - 12

    # Сверху: difficulty marker (3px) + LV (мелкий) + rank (справа).
    diff_color = DIFFICULTY_COLORS.get(item.difficulty, DIFFICULTY_COLORS["MASTER"])
    _diff_marker(canvas, tx, y + 14, diff_color)
    lv_font = skia.Font(fonts.get("mono"), 11)
    canvas.drawString(
        f"LV {item.level:g}",
        tx + 9,
        y + 23,
        lv_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_DIM),
    )
    # Difficulty short name справа от LV (тонкая uppercase).
    diff_short = item.difficulty.replace("RE:MASTER", "RE:M")
    diff_font = skia.Font(fonts.get("ui-bold"), 10)
    canvas.drawString(
        diff_short,
        tx + 9 + lv_font.measureText(f"LV {item.level:g}") + 8,
        y + 23,
        diff_font,
        skia.Paint(AntiAlias=True, Color4f=diff_color),
    )

    # Rank — top right corner. Точка + текст.
    rank_color = RANK_COLORS.get(item.rank, C_TEXT_FAINT)
    canvas.drawCircle(
        x + CARD_W_B35 - 12 - 4, y + 18, 3, skia.Paint(AntiAlias=True, Color4f=rank_color)
    )
    _text_right(
        canvas, item.rank, x + CARD_W_B35 - 24, y + 22, 11, color=rank_color, role="ui-bold"
    )

    # Title — посередине, ellipsized.
    title_font = skia.Font(fonts.get("cjk-bold"), 14)
    title = _ellipsized(title_font, item.title or f"#{item.music_id}", inner_w - 8)
    canvas.drawString(title, tx, y + 44, title_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI))

    # Achievement — крупно (mono), белый. Уменьшен до 17pt — даёт место contrib.
    ach_font = skia.Font(fonts.get("mono-bold"), 17)
    canvas.drawString(
        f"{item.achievement:.4f}%",
        tx,
        y + 70,
        ach_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
    )

    # Contribution — bottom-right, акцентный, крупный.
    contrib_font = skia.Font(fonts.get("mono-bold"), 16)
    contrib = f"{item.rating_contribution}"
    cw = contrib_font.measureText(contrib)
    canvas.drawString(
        contrib,
        x + CARD_W_B35 - cw - 12,
        y + 70,
        contrib_font,
        skia.Paint(AntiAlias=True, Color4f=C_ACCENT),
    )

    # Index — bottom-right самый край, мелкий, faint, под contribution.
    idx_font = skia.Font(fonts.get("mono"), 9.5)
    idx_text = f"#{idx:02d}"
    canvas.drawString(
        idx_text,
        x + CARD_W_B35 - idx_font.measureText(idx_text) - 12,
        y + CARD_H_B35 - 6,
        idx_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT),
    )


def _draw_card_b15(
    canvas: skia.Canvas, x: float, y: float, item: RatingItem, image: skia.Image | None, idx: int
) -> None:
    _surface(canvas, skia.Rect.MakeXYWH(x, y, CARD_W_B15, CARD_H_B15), radius=12)

    jacket_size = 48.0
    _jacket(canvas, image, x + 12, y + 12, jacket_size)

    tx = x + 12 + jacket_size + 14
    inner_w = CARD_W_B15 - (tx - x) - 12

    diff_color = DIFFICULTY_COLORS.get(item.difficulty, DIFFICULTY_COLORS["MASTER"])
    _diff_marker(canvas, tx, y + 13, diff_color)

    lv_font = skia.Font(fonts.get("mono"), 11)
    canvas.drawString(
        f"LV {item.level:g}",
        tx + 9,
        y + 22,
        lv_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_DIM),
    )
    diff_short = item.difficulty.replace("RE:MASTER", "RE:M")
    diff_font = skia.Font(fonts.get("ui-bold"), 10)
    canvas.drawString(
        diff_short,
        tx + 9 + lv_font.measureText(f"LV {item.level:g}") + 8,
        y + 22,
        diff_font,
        skia.Paint(AntiAlias=True, Color4f=diff_color),
    )

    # Title.
    title_font = skia.Font(fonts.get("cjk-bold"), 14)
    title = _ellipsized(title_font, item.title or f"#{item.music_id}", inner_w - 100)
    canvas.drawString(title, tx, y + 42, title_font, skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI))

    # Achievement.
    ach_font = skia.Font(fonts.get("mono-bold"), 18)
    canvas.drawString(
        f"{item.achievement:.4f}%",
        tx,
        y + 62,
        ach_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
    )

    # Rank + index в правой колонке.
    rank_color = RANK_COLORS.get(item.rank, C_TEXT_FAINT)
    canvas.drawCircle(
        x + CARD_W_B15 - 12 - 4, y + 18, 3, skia.Paint(AntiAlias=True, Color4f=rank_color)
    )
    _text_right(
        canvas, item.rank, x + CARD_W_B15 - 24, y + 22, 11, color=rank_color, role="ui-bold"
    )

    # Contribution — справа крупно, акцентный, без RT eyebrow.
    contrib_font = skia.Font(fonts.get("mono-bold"), 18)
    contrib = f"{item.rating_contribution}"
    cw = contrib_font.measureText(contrib)
    canvas.drawString(
        contrib,
        x + CARD_W_B15 - cw - 12,
        y + 50,
        contrib_font,
        skia.Paint(AntiAlias=True, Color4f=C_ACCENT),
    )

    # Index — bottom-right.
    idx_font = skia.Font(fonts.get("mono"), 10)
    idx_text = f"#{idx:02d}"
    canvas.drawString(
        idx_text,
        x + CARD_W_B15 - idx_font.measureText(idx_text) - 12,
        y + CARD_H_B15 - 8,
        idx_font,
        skia.Paint(AntiAlias=True, Color4f=C_TEXT_FAINT),
    )


# ──────────────── публичный render ────────────────


def render(inp: RatingFrameInput) -> bytes:
    fonts.preload()
    surface = skia.Surface(W, H)
    with surface as canvas:
        _background(canvas)

        # ════ Hero (top, full width) ════
        hero_x, hero_y = MARGIN, MARGIN
        hero_w, hero_h = W - 2 * MARGIN, HERO_H
        _surface(canvas, skia.Rect.MakeXYWH(hero_x, hero_y, hero_w, hero_h), radius=20)

        # Left column: username + tagline.
        _label(canvas, "PLAYER", hero_x + 28, hero_y + 32)
        _text(canvas, inp.username, hero_x + 28, hero_y + 78, 48, role="display")
        _text(
            canvas,
            inp.brand + " · best35 + best15",
            hero_x + 28,
            hero_y + 108,
            14,
            color=C_TEXT_FAINT,
            role="ui",
        )

        # Middle: total rating — гигантское моно-число (акцент).
        rating_label_x = hero_x + 540
        _label(canvas, "RATING", rating_label_x, hero_y + 32)
        rating_font = skia.Font(fonts.get("mono-bold"), 88)
        rating_str = str(inp.rating)
        rw = rating_font.measureText(rating_str)
        canvas.drawString(
            rating_str,
            rating_label_x,
            hero_y + 110,
            rating_font,
            skia.Paint(AntiAlias=True, Color4f=C_ACCENT),
        )

        # Тонкий вертикальный divider.
        divider_x = rating_label_x + rw + 56
        canvas.drawRect(
            skia.Rect.MakeXYWH(divider_x, hero_y + 28, 1, hero_h - 56),
            skia.Paint(AntiAlias=True, Color4f=C_DIVIDER),
        )

        # Right: полезные метрики — AVG ACH / SSS+ count / TOP LV.
        all_items = list(inp.b35) + list(inp.b15)
        n = max(len(all_items), 1)
        avg_ach = sum(it.achievement for it in all_items) / n
        sss_plus = sum(1 for it in all_items if it.rank == "SSS+")
        top_lv = max((it.level for it in all_items), default=0.0)

        stats_x = divider_x + 36
        stat_gap = 200
        stats = (
            ("AVG ACH", f"{avg_ach:.3f}%"),
            ("SSS+", str(sss_plus)),
            ("TOP LV", f"{top_lv:g}"),
        )
        for i, (label, val) in enumerate(stats):
            sx = stats_x + i * stat_gap
            _label(canvas, label, sx, hero_y + 32)
            val_font = skia.Font(fonts.get("mono-bold"), 36)
            canvas.drawString(
                val,
                sx,
                hero_y + 78,
                val_font,
                skia.Paint(AntiAlias=True, Color4f=C_TEXT_HI),
            )

        # Дата/timestamp в правом верхнем углу hero — мелко.
        _text_right(
            canvas,
            f"{len(inp.b35)} + {len(inp.b15)} карт",
            hero_x + hero_w - 28,
            hero_y + 38,
            12,
            color=C_TEXT_FAINT,
            role="mono",
        )

        # ════ B35 grid ════
        section_y = MARGIN + HERO_H + 32
        _label(canvas, f"B35  ·  СУММА {inp.b35_sum}", MARGIN, section_y)
        _text_right(
            canvas,
            "ТОП 35 ПО ОЦЕНКЕ",
            W - MARGIN,
            section_y,
            10.5,
            color=C_TEXT_FAINT,
            role="ui-bold",
        )

        grid_y = section_y + 16
        for i, (item, image) in enumerate(zip(inp.b35, inp.jackets_b35, strict=False)):
            if i >= B35_COLS * B35_ROWS:
                break
            col = i % B35_COLS
            row = i // B35_COLS
            x = MARGIN + col * (CARD_W_B35 + GUTTER)
            y = grid_y + row * (CARD_H_B35 + GUTTER)
            _draw_card_b35(canvas, x, y, item, image, i + 1)

        # ════ B15 grid ════
        b35_end_y = grid_y + B35_ROWS * CARD_H_B35 + (B35_ROWS - 1) * GUTTER
        section2_y = b35_end_y + 28
        _label(canvas, f"B15  ·  СУММА {inp.b15_sum}", MARGIN, section2_y)
        _text_right(
            canvas,
            "ТОП 15 ИЗ НОВОЙ ВЕРСИИ",
            W - MARGIN,
            section2_y,
            10.5,
            color=C_TEXT_FAINT,
            role="ui-bold",
        )

        grid2_y = section2_y + 16
        for i, (item, image) in enumerate(zip(inp.b15, inp.jackets_b15, strict=False)):
            if i >= B15_COLS * B15_ROWS:
                break
            col = i % B15_COLS
            row = i // B15_COLS
            x = MARGIN + col * (CARD_W_B15 + GUTTER)
            y = grid2_y + row * (CARD_H_B15 + GUTTER)
            _draw_card_b15(canvas, x, y, item, image, 35 + i + 1)

    image = surface.makeImageSnapshot()
    return bytes(image.encodeToData(skia.kPNG, 95))
