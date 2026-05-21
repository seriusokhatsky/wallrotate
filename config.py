"""Завантаження/збереження налаштувань та шляхи додатку.

Налаштування зберігаються у ~/Library/Application Support/WallRotate/config.json
Кеш зображень — у ~/Library/Application Support/WallRotate/cache/
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

APP_NAME = "WallRotate"

SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
CONFIG_PATH = SUPPORT_DIR / "config.json"
CACHE_DIR = SUPPORT_DIR / "cache"

DEFAULTS = {
    "interval_seconds": 3600,        # раз на годину
    "provider": "unsplash",          # "unsplash" | "framedsc"
    "query": "nature,landscape",     # тема пошуку для Unsplash (через кому = випадково)
    "orientation": "landscape",      # landscape | portrait | squarish (тільки Unsplash)
    "same_on_all_monitors": True,
    "cache_limit": 20,               # скільки фото тримати в кеші
    "paused": False,
    "unsplash_access_key": "",       # можна задати з меню додатку
    # --- Hall of FRAMED фільтри ---
    "framedsc_min_score": 0,         # мінімальний score (0 = будь-який)
    "framedsc_include_games": "",    # часткові назви через кому (порожньо = всі)
    "framedsc_exclude_games": "",    # часткові назви через кому (порожньо = нічого)
    "framedsc_color_group": "",      # назва групи кольору або порожньо = Any
}


def ensure_dirs() -> None:
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Повертає конфіг з дефолтами, доповненими збереженими значеннями."""
    ensure_dirs()
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = {}
    return {**DEFAULTS, **data}


def save_config(cfg: dict) -> None:
    """Атомарний запис: спочатку у тимчасовий файл, потім os.replace.

    Запобігає втраті налаштувань, якщо процес впаде посередині запису —
    у такому разі лишиться або старий config.json, або новий, але не обрізаний.
    """
    ensure_dirs()
    payload = json.dumps(cfg, indent=2, ensure_ascii=False)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".config-", suffix=".tmp", dir=str(SUPPORT_DIR)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, CONFIG_PATH)
    except Exception:
        # Прибрати tmp при будь-якій помилці, щоб не лишати сміття
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
