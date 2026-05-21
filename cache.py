"""Завантаження зображень у локальний кеш і контроль його розміру."""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from models import Photo


def _safe_cache_name(photo_id: str) -> str:
    """SHA1 від photo.id — гарантує безпечне ім'я файла у кеші.

    Закриває одразу дві проблеми:
      1. Path traversal: provider може повернути id виду "../../../etc/passwd"
         — після хешування лишаться лише символи [0-9a-f], запис поза dest_dir
         неможливий.
      2. AppleScript injection: шлях файла потрапляє у fallback-скрипт у
         wallpaper.py через f-string з лапками; якщо id містить " або \\,
         AppleScript ламається. Хеш гарантує, що в імені цих символів немає.

    Хеш детермінований, тож кеш-гіт для того ж самого id зберігається.
    """
    return hashlib.sha1(photo_id.encode("utf-8")).hexdigest()


def download_photo(photo: Photo, dest_dir: Path, timeout: int = 60) -> Path:
    """Завантажити повне зображення у dest_dir. Повертає шлях до файлу.

    Якщо файл з таким id уже є — повторно не качаємо.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{_safe_cache_name(photo.id)}.jpg"

    if path.exists() and path.stat().st_size > 0:
        return path

    resp = requests.get(photo.full_url, timeout=timeout, stream=True)
    resp.raise_for_status()
    tmp = path.with_suffix(".part")
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)
    tmp.replace(path)
    return path


def enforce_limit(dest_dir: Path, limit: int) -> None:
    """Лишити в кеші не більше `limit` найновіших файлів."""
    dest_dir = Path(dest_dir)
    if not dest_dir.exists():
        return
    files = sorted(dest_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
    excess = len(files) - max(0, limit)
    for old in files[:excess]:
        try:
            old.unlink()
        except OSError:
            pass
