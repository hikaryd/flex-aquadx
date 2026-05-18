"""Загрузка Typeface для рендера. Lazy-init с кэшированием, graceful fallback на system default."""

from __future__ import annotations

import hashlib
from glob import glob
from pathlib import Path

import skia

from aquadx.utils.logging import get_logger

log = get_logger("aquadx.render.fonts")

# Корень с .ttf/.otf файлами.
FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

# Логические роли → имена файлов (приоритет в порядке списка). Если файл не
# найден, Skia подставит default через `skia.Typeface()`.
# Поддерживаем как variable fonts (один файл на семейство), так и static.
_FONT_ROLES: dict[str, tuple[str, ...]] = {
    "display": ("Inter.ttf", "InterTight-Bold.ttf", "Inter-Bold.ttf"),
    "display-semibold": ("Inter.ttf", "InterTight-SemiBold.ttf", "Inter-SemiBold.ttf"),
    "ui": ("Inter.ttf", "Inter-Regular.ttf"),
    "ui-bold": ("Inter.ttf", "Inter-Bold.ttf"),
    "mono": ("JetBrainsMono.ttf", "JetBrainsMono-Medium.ttf"),
    "mono-bold": ("JetBrainsMono.ttf", "JetBrainsMono-Bold.ttf"),
    "cjk": ("NotoSansJP.ttf", "NotoSansJP-Regular.ttf"),
    "cjk-bold": ("NotoSansJP.ttf", "NotoSansJP-Bold.ttf"),
}


_cache: dict[str, skia.Typeface] = {}
_font_pack_hash: str | None = None


def _load_role(role: str) -> skia.Typeface:
    for filename in _FONT_ROLES.get(role, ()):
        path = FONTS_DIR / filename
        if path.exists():
            tf = skia.Typeface.MakeFromFile(str(path))
            if tf is not None:
                return tf
    log.debug("font_role_fallback_default", role=role)
    return skia.Typeface()


def get(role: str) -> skia.Typeface:
    """Вернуть Typeface для логической роли (`display`, `ui`, `mono`, `cjk`...)."""
    if role not in _cache:
        _cache[role] = _load_role(role)
    return _cache[role]


def preload() -> None:
    """Прогреть все известные роли. Безопасно вызывать многократно."""
    for role in _FONT_ROLES:
        get(role)


def font_pack_hash() -> str:
    """sha256 от содержимого всех .ttf/.otf в assets/fonts, первые 16 hex.

    Стабилен между вызовами в рамках процесса (вычисляется лениво один раз).
    Включается в ETag PNG, чтобы апгрейд шрифтов инвалидировал кэш.
    """
    global _font_pack_hash
    if _font_pack_hash is None:
        h = hashlib.sha256()
        paths = sorted(glob(str(FONTS_DIR / "*.ttf"))) + sorted(glob(str(FONTS_DIR / "*.otf")))
        for p in paths:
            with open(p, "rb") as f:
                h.update(f.read())
        _font_pack_hash = h.hexdigest()[:16] or "no-fonts-installed"
    return _font_pack_hash
