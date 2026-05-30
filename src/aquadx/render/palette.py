"""Цветовая палитра рендера: editorial dark, single accent.

Дизайн-направление: Linear/Vercel-минимализм 2025.
Никаких градиентных пятен, никаких glow-облаков — только solid surfaces,
тонкие границы (1px ≤ 8% alpha), один акцентный цвет.
"""

from __future__ import annotations

import skia

# Базовый фон — графитово-навиди.
C_BG = skia.ColorSetRGB(0x0A, 0x0B, 0x10)
C_BG_TOP = C_BG

# Поверхности карточек: тонкие dark-glass плитки, но без мутного
# "серое на сером" — Telegram сильно пережимает тёмные полутона.
C_SURFACE = skia.Color4f(1.0, 1.0, 1.0, 0.050)
C_SURFACE_HI = skia.Color4f(1.0, 1.0, 1.0, 0.075)
C_GLASS_BORDER = skia.Color4f(1.0, 1.0, 1.0, 0.13)
C_DIVIDER = skia.Color4f(1.0, 1.0, 1.0, 0.11)

# Иерархия текста: pure white → readable muted.
# Secondary text must stay readable after Telegram downscaling/compression.
C_TEXT_HI = skia.Color4f(0.98, 0.98, 1.0, 1.0)
C_TEXT_DIM = skia.Color4f(0.83, 0.85, 0.90, 1.0)
C_TEXT_FAINT = skia.Color4f(0.65, 0.68, 0.75, 1.0)

# Единственный акцент — холодный мятно-лайм. Используется ТОЛЬКО для
# ключевых чисел (rating, achievement, contribution). Не для декора.
C_ACCENT = skia.Color4f(0.71, 1.0, 0.42, 1.0)  # #B6FF6B
C_ACCENT_DIM = skia.Color4f(0.71, 1.0, 0.42, 0.35)
C_ACH_A = C_ACCENT

# Difficulty: 4px-маркер слева от пилюли. Сам текст белый.
DIFFICULTY_COLORS: dict[str, skia.Color4f] = {
    "BASIC": skia.Color4f(0.40, 0.90, 0.55, 1.0),
    "ADVANCED": skia.Color4f(1.00, 0.78, 0.20, 1.0),
    "EXPERT": skia.Color4f(0.95, 0.40, 0.45, 1.0),
    "MASTER": skia.Color4f(0.62, 0.45, 1.00, 1.0),
    "RE:MASTER": skia.Color4f(0.95, 0.85, 1.00, 1.0),
    "UTAGE": skia.Color4f(0.95, 0.45, 0.95, 1.0),
}

# Rank: мягкие, но узнаваемые тинты для маленького индикатора.
RANK_COLORS: dict[str, skia.Color4f] = {
    "SSS+": C_ACCENT,
    "SSS": skia.Color4f(0.95, 0.85, 0.45, 1.0),
    "SS+": skia.Color4f(0.95, 0.70, 0.40, 1.0),
    "SS": skia.Color4f(0.85, 0.60, 0.40, 1.0),
    "S+": skia.Color4f(0.70, 0.55, 0.40, 1.0),
    "S": skia.Color4f(0.60, 0.50, 0.45, 1.0),
}

# Judgements (TrackResult): теплый-холодный градиент по строгости.
JUDGEMENT_COLORS: dict[str, skia.Color4f] = {
    "CRIT": C_ACCENT,
    "PERFECT": skia.Color4f(0.95, 0.85, 0.45, 1.0),
    "GREAT": skia.Color4f(0.55, 0.85, 1.00, 1.0),
    "GOOD": skia.Color4f(0.55, 0.60, 0.75, 1.0),
    "MISS": skia.Color4f(0.95, 0.40, 0.45, 1.0),
}
