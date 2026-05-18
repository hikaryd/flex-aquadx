"""Цветовая палитра рендера. Single source of truth для всех шаблонов."""

from __future__ import annotations

import skia

# Базовый фон: глубокий пурпур → миднайт.
C_BG_TOP = skia.ColorSetRGB(0x18, 0x0F, 0x2E)
C_BG_BOT = skia.ColorSetRGB(0x08, 0x06, 0x14)

# Акцентные пятна gradient mesh.
C_MESH_VIOLET = skia.Color4f(0.55, 0.30, 0.95, 1.0)
C_MESH_PINK = skia.Color4f(0.95, 0.35, 0.65, 1.0)
C_MESH_CYAN = skia.Color4f(0.20, 0.85, 0.95, 1.0)

# Glassmorphism слои.
C_GLASS_FILL = skia.Color4f(0.07, 0.05, 0.16, 0.55)
C_GLASS_OVER = skia.Color4f(1.0, 1.0, 1.0, 0.04)
C_GLASS_BORDER = skia.Color4f(1.0, 1.0, 1.0, 0.10)

# Текст: иерархия яркости.
C_TEXT_HI = skia.Color4f(1.0, 1.0, 1.0, 1.0)
C_TEXT_DIM = skia.Color4f(0.78, 0.74, 0.92, 1.0)
C_TEXT_FAINT = skia.Color4f(0.55, 0.50, 0.72, 1.0)

# Achievement gradient pink → cyan.
C_ACH_A = skia.Color4f(1.0, 0.45, 0.72, 1.0)
C_ACH_B = skia.Color4f(0.50, 0.85, 1.0, 1.0)

# Цвета пилюль difficulty (порядок DIFFICULTY_NAMES).
DIFFICULTY_COLORS: dict[str, skia.Color4f] = {
    "BASIC": skia.Color4f(0.30, 0.85, 0.55, 0.90),
    "ADVANCED": skia.Color4f(1.00, 0.78, 0.20, 0.90),
    "EXPERT": skia.Color4f(0.95, 0.40, 0.40, 0.90),
    "MASTER": skia.Color4f(0.55, 0.20, 0.95, 0.90),
    "RE:MASTER": skia.Color4f(0.95, 0.85, 1.00, 0.95),
    "UTAGE": skia.Color4f(0.95, 0.25, 0.85, 0.90),
}

# Цвета пилюль рангов.
RANK_COLORS: dict[str, skia.Color4f] = {
    "SSS+": skia.Color4f(1.00, 0.45, 0.72, 1.0),
    "SSS": skia.Color4f(0.95, 0.55, 0.30, 1.0),
    "SS+": skia.Color4f(0.95, 0.45, 0.20, 1.0),
    "SS": skia.Color4f(0.85, 0.40, 0.20, 1.0),
    "S+": skia.Color4f(0.70, 0.35, 0.20, 1.0),
    "S": skia.Color4f(0.55, 0.30, 0.20, 1.0),
}

# Цвета чипов judgements в TrackResult.
JUDGEMENT_COLORS: dict[str, skia.Color4f] = {
    "CRIT": skia.Color4f(1.00, 0.78, 0.30, 1.0),
    "PERFECT": skia.Color4f(1.00, 0.55, 0.30, 1.0),
    "GREAT": skia.Color4f(0.40, 0.95, 0.55, 1.0),
    "GOOD": skia.Color4f(0.40, 0.65, 1.0, 1.0),
    "MISS": skia.Color4f(0.75, 0.70, 0.85, 1.0),
}
