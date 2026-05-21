"""Абстракція джерела зображень.

Щоб додати нове джерело (Pexels, Pixabay, локальна тека тощо),
достатньо реалізувати цей інтерфейс і зареєструвати провайдера.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from models import Photo


class ImageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_random(self, query: Optional[str] = None,
                   orientation: str = "landscape") -> Photo:
        """Повернути одне випадкове фото за заданими параметрами."""
        raise NotImplementedError

    def on_applied(self, photo: Photo) -> None:
        """Викликається після того, як фото стало шпалерою.

        Наприклад, Unsplash тут тригерить лічильник завантажень.
        За замовчуванням — нічого не робить.
        """
        return None

    def attribution_url(self, link: str) -> str:
        """Посилання для атрибуції (може додавати UTM). За замовчуванням без змін."""
        return link
