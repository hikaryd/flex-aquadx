"""Детерминированные ETag и кэш-ключи для рендера PNG."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from aquadx.render.fonts import font_pack_hash

# Версия шаблона; bump при изменении layout или стилей карточки.
TEMPLATE_VERSION = "1"


def compute_etag(endpoint: str, dto: Any, *, scale: int = 1) -> str:
    """sha256(template_version + font_pack_hash + canonical_dto + scale)[:16].

    DTO канонизируется через model_dump(mode='json') + json.dumps(sort_keys=True),
    чтобы порядок ключей и unicode-нормализация не влияли на ETag.
    """
    if hasattr(dto, "model_dump"):
        payload_obj = dto.model_dump(mode="json")
    elif hasattr(dto, "__dict__"):
        payload_obj = dto.__dict__
    else:
        payload_obj = dto
    payload = json.dumps(payload_obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    h = hashlib.sha256()
    h.update(TEMPLATE_VERSION.encode())
    h.update(b"|")
    h.update(font_pack_hash().encode())
    h.update(b"|")
    h.update(endpoint.encode())
    h.update(b"|")
    h.update(payload.encode("utf-8"))
    h.update(f"|{scale}".encode())
    return h.hexdigest()[:16]


def image_cache_key(endpoint: str, etag: str) -> str:
    return f"image|{endpoint}|{etag}"


def jacket_404_key(url: str) -> str:
    return f"jacket-404|{hashlib.sha256(url.encode()).hexdigest()[:16]}"
