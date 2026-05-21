"""Провайдер Hall of FRAMED (framedsc.com).

Дані завантажуються з двох публічних JSON-файлів на GitHub:
  * shotsdb.json  — список скріншотів (ID, shotUrl, gameName, author, spoiler …)
  * authorsdb.json — дані авторів (authorNick, authorid, socials …)

Офіційного API немає, тому використовується пряме завантаження JSON.
Дані кешуються у памʼяті протягом CACHE_TTL_SECONDS, щоб не завантажувати
файл (~1 МБ) щоразу при зміні шпалери.
"""
from __future__ import annotations

import random
import time
from typing import Optional

import requests

from models import Photo
from providers.base import ImageProvider

SHOTS_URL = (
    "https://raw.githubusercontent.com/originalnicodrgitbot/"
    "hall-of-framed-db/main/shotsdb.json"
)
AUTHORS_URL = (
    "https://raw.githubusercontent.com/originalnicodrgitbot/"
    "hall-of-framed-db/main/authorsdb.json"
)

HOF_BASE_URL = "https://framedsc.com/HallOfFramed/"

# Скільки секунд тримати дані в памʼяті (1 година)
CACHE_TTL_SECONDS = 3600


class FramedSCProvider(ImageProvider):
    name = "framedsc"

    def __init__(self, timeout: int = 30, skip_spoilers: bool = True):
        self.timeout = timeout
        self.skip_spoilers = skip_spoilers

        # Кеш даних у памʼяті
        self._shots: list[dict] = []
        self._authors: dict[str, dict] = {}   # authorid -> author dict
        self._cached_at: float = 0.0

    # --- кеш ---

    def _is_cache_fresh(self) -> bool:
        return (
            bool(self._shots)
            and (time.monotonic() - self._cached_at) < CACHE_TTL_SECONDS
        )

    def _load_data(self) -> None:
        """Завантажити shotsdb + authorsdb і заповнити кеш."""
        shots_resp = requests.get(SHOTS_URL, timeout=self.timeout)
        shots_resp.raise_for_status()
        shots_raw = shots_resp.json().get("_default", {})

        authors_resp = requests.get(AUTHORS_URL, timeout=self.timeout)
        authors_resp.raise_for_status()
        authors_raw = authors_resp.json().get("_default", {})

        # Індекс авторів за Discord ID
        self._authors = {
            entry["authorid"]: entry
            for entry in authors_raw.values()
            if isinstance(entry, dict) and "authorid" in entry
        }

        # Список придатних скріншотів
        shots = list(shots_raw.values())
        if self.skip_spoilers:
            shots = [s for s in shots if not s.get("spoiler", False)]
        # Залишаємо тільки горизонтальні (width > height) з URL зображення
        self._shots = [
            s for s in shots
            if s.get("shotUrl") and s.get("width", 0) > s.get("height", 0)
        ]
        self._cached_at = time.monotonic()

    def _ensure_data(self) -> None:
        if not self._is_cache_fresh():
            self._load_data()

    # --- допоміжне ---

    def _resolve_author(self, shot: dict) -> tuple[str, str]:
        """Повернути (author_name, author_link) для знімку."""
        author_id = shot.get("author", "")
        author = self._authors.get(author_id)
        if not author:
            return ("Unknown", HOF_BASE_URL)

        name = author.get("authorNick") or "Unknown"
        socials = author.get("socials") or []
        link = socials[0] if socials else HOF_BASE_URL
        return (name, link)

    # --- інтерфейс ImageProvider ---

    def get_random(self, query: Optional[str] = None,
                   orientation: str = "landscape") -> Photo:
        """Повернути випадковий скріншот з Hall of FRAMED.

        Параметри query та orientation ігноруються (колекція не підтримує
        фільтрацію за ключовими словами), але зберігаються для сумісності
        з інтерфейсом.
        """
        self._ensure_data()
        if not self._shots:
            raise RuntimeError("Hall of FRAMED: no shots available after loading data.")

        shot = random.choice(self._shots)
        author_name, author_link = self._resolve_author(shot)

        return Photo(
            id=str(shot.get("ID", shot.get("epochTime", ""))),
            full_url=shot["shotUrl"],
            author_name=author_name,
            author_link=author_link,
            description=shot.get("gameName"),
            download_location=None,
            source=self.name,
        )
