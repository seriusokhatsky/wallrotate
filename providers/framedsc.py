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

# Групи кольорів CSS colorName -> список значень з бази
COLOR_GROUPS: dict[str, list[str]] = {
    "Neutral (greys)": [
        "silver", "lightgrey", "darkgrey", "gainsboro", "dimgrey", "grey",
        "whitesmoke", "lavender", "white", "snow", "linen", "beige",
        "aliceblue", "mintcream", "oldlace", "cornsilk", "gray", "darkgray",
        "slategrey", "lightslategrey", "slategray",
    ],
    "Warm / Brown": [
        "tan", "rosybrown", "peru", "burlywood", "sienna", "wheat",
        "sandybrown", "chocolate", "darksalmon", "saddlebrown", "brown",
        "darkkhaki", "khaki", "palegoldenrod", "darkgoldenrod", "goldenrod",
        "navajowhite", "bisque", "peachpuff", "moccasin", "antiquewhite",
        "lightsalmon", "lightcoral", "indianred", "lightsteelblue",
    ],
    "Red / Pink": [
        "firebrick", "crimson", "tomato", "maroon", "red", "darkred",
        "coral", "orangered", "pink", "lightpink", "palevioletred",
        "mediumvioletred", "deeppink", "salmon", "mistyrose",
    ],
    "Blue / Teal": [
        "cadetblue", "steelblue", "skyblue", "powderblue", "lightblue",
        "darkslateblue", "teal", "cornflowerblue", "midnightblue",
        "dodgerblue", "royalblue", "deepskyblue", "darkcyan",
        "paleturquoise", "lightcyan", "lightskyblue", "mediumturquoise",
        "darkturquoise", "lightseagreen",
    ],
    "Green": [
        "darkolivegreen", "darkseagreen", "seagreen", "mediumaquamarine",
        "olivedrab", "yellowgreen", "lightgreen", "mediumseagreen",
    ],
    "Purple": [
        "thistle", "plum", "orchid", "darkorchid", "mediumorchid",
        "mediumpurple", "violet", "slateblue",
    ],
    "Orange / Yellow": [
        "orange", "gold", "darkorange", "palegoldenrod", "lightyellow",
    ],
}


class FramedSCProvider(ImageProvider):
    name = "framedsc"

    def __init__(
        self,
        timeout: int = 30,
        skip_spoilers: bool = True,
        min_score: int = 0,
        include_games: Optional[list[str]] = None,
        exclude_games: Optional[list[str]] = None,
        color_group: Optional[str] = None,
    ):
        self.timeout = timeout
        self.skip_spoilers = skip_spoilers
        self.min_score = min_score
        self.include_games = [g.lower().strip() for g in (include_games or []) if g.strip()]
        self.exclude_games = [g.lower().strip() for g in (exclude_games or []) if g.strip()]
        self.color_group = color_group  # None = будь-який

        # _all_shots — горизонтальні, без spoiler (база без фільтрів користувача)
        self._all_shots: list[dict] = []
        # _shots — після фільтрів score / games / color
        self._shots: list[dict] = []
        self._authors: dict[str, dict] = {}
        self._cached_at: float = 0.0

    # --- кеш ---

    def _is_cache_fresh(self) -> bool:
        return (
            bool(self._all_shots)
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

        # База: горизонтальні, без spoiler, з URL
        shots = list(shots_raw.values())
        if self.skip_spoilers:
            shots = [s for s in shots if not s.get("spoiler", False)]
        self._all_shots = [
            s for s in shots
            if s.get("shotUrl") and s.get("width", 0) > s.get("height", 0)
        ]
        self._cached_at = time.monotonic()
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Фільтрує _all_shots за score / games / color -> _shots."""
        shots = self._all_shots

        if self.min_score > 0:
            shots = [s for s in shots if s.get("score", 0) >= self.min_score]

        if self.include_games:
            shots = [
                s for s in shots
                if any(g in (s.get("gameName") or "").lower() for g in self.include_games)
            ]

        if self.exclude_games:
            shots = [
                s for s in shots
                if not any(g in (s.get("gameName") or "").lower() for g in self.exclude_games)
            ]

        if self.color_group and self.color_group in COLOR_GROUPS:
            allowed = set(COLOR_GROUPS[self.color_group])
            shots = [s for s in shots if (s.get("colorName") or "").lower() in allowed]

        self._shots = shots

    def _ensure_data(self) -> None:
        if not self._is_cache_fresh():
            self._load_data()

    def update_filters(
        self,
        min_score: int = 0,
        include_games: Optional[list[str]] = None,
        exclude_games: Optional[list[str]] = None,
        color_group: Optional[str] = None,
    ) -> None:
        """Змінити фільтри без повторного завантаження даних."""
        self.min_score = min_score
        self.include_games = [g.lower().strip() for g in (include_games or []) if g.strip()]
        self.exclude_games = [g.lower().strip() for g in (exclude_games or []) if g.strip()]
        self.color_group = color_group
        if self._all_shots:            # якщо дані вже є — фільтруємо одразу
            self._apply_filters()

    @property
    def shot_count(self) -> int:
        return len(self._shots)

    # --- допоміжне ---

    def _resolve_author(self, shot: dict) -> tuple[str, str]:
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
        self._ensure_data()
        if not self._shots:
            raise RuntimeError(
                "Hall of FRAMED: no shots match current filters. "
                "Try relaxing the score / color / game filters."
            )
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
