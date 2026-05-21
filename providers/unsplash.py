"""Провайдер Unsplash.

Дотримується правил Unsplash API:
  * фото беремо з urls.full (hotlinking);
  * після застосування тригеримо links.download_location;
  * для атрибуції додаємо UTM-параметри.

Docs: https://unsplash.com/documentation
Guidelines: https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines
"""
from __future__ import annotations

import random
from typing import Optional

import requests

from models import Photo
from providers.base import ImageProvider

API_BASE = "https://api.unsplash.com"


class UnsplashProvider(ImageProvider):
    name = "unsplash"

    def __init__(self, access_key: str, app_name: str = "WallRotate", timeout: int = 20):
        self.access_key = access_key
        self.app_name = app_name
        self.timeout = timeout

    # --- внутрішнє ---
    def _headers(self) -> dict:
        return {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1",
        }

    @staticmethod
    def _pick_query(query: Optional[str]) -> Optional[str]:
        """Якщо тема задана списком через кому — обрати випадкову."""
        if not query:
            return None
        parts = [p.strip() for p in query.split(",") if p.strip()]
        return random.choice(parts) if parts else None

    def _photo_from_data(self, data: dict) -> Photo:
        """Розбір JSON-відповіді /photos/random у модель Photo.

        Винесено окремо, щоб логіку парсингу можна було тестувати без мережі.
        """
        return Photo(
            id=data["id"],
            full_url=data["urls"]["full"],
            author_name=data.get("user", {}).get("name", "Unknown"),
            author_link=data.get("user", {}).get("links", {}).get("html", "https://unsplash.com"),
            description=data.get("description") or data.get("alt_description"),
            download_location=data.get("links", {}).get("download_location"),
            source=self.name,
        )

    # --- інтерфейс ImageProvider ---
    def get_random(self, query: Optional[str] = None,
                   orientation: str = "landscape") -> Photo:
        params = {}
        chosen = self._pick_query(query)
        if chosen:
            params["query"] = chosen
        if orientation:
            params["orientation"] = orientation

        resp = requests.get(
            f"{API_BASE}/photos/random",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # /photos/random без параметра count повертає один обʼєкт.
        if isinstance(data, list):
            data = data[0]
        return self._photo_from_data(data)

    def on_applied(self, photo: Photo) -> None:
        """Тригер download-endpoint (вимога Unsplash API). Помилки не критичні."""
        if not photo.download_location:
            return
        try:
            requests.get(photo.download_location, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException:
            pass

    def attribution_url(self, link: str) -> str:
        if not link:
            return link
        sep = "&" if "?" in link else "?"
        return f"{link}{sep}utm_source={self.app_name}&utm_medium=referral"
