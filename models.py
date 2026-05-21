"""Дата-моделі додатку."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Photo:
    """Одне фото, нормалізоване з відповіді будь-якого провайдера."""

    id: str
    full_url: str            # пряме посилання на файл для завантаження (Unsplash: urls.full)
    author_name: str
    author_link: str         # посилання на профіль автора (для атрибуції)
    description: Optional[str] = None
    # Технічний ендпоінт Unsplash для інкременту лічильника завантажень.
    # Для інших джерел може бути None.
    download_location: Optional[str] = None
    source: str = "unknown"  # назва провайдера, напр. "unsplash"
