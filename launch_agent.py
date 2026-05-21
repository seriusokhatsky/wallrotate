"""Автозапуск при вході в систему через LaunchAgent.

Створює/видаляє plist у ~/Library/LaunchAgents. Працює як для запуску зі
скрипта (`python3 app.py`), так і для зібраного .app (py2app).

Увімкнення = створення plist; набуде чинності при наступному вході в систему
(щоб не плодити другий екземпляр поверх уже запущеного зараз).
Вимкнення = видалення plist (+ спроба вивантажити, якщо вже завантажений).
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.example.wallrotate"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"


def _is_app_bundle() -> bool:
    return bool(getattr(sys, "frozen", False)) or ".app/Contents/" in sys.executable


def program_arguments() -> list:
    """Команда запуску для LaunchAgent — залежить від режиму."""
    if _is_app_bundle():
        # У зібраному .app sys.executable — головний бінарник усередині бандлу.
        return [sys.executable]
    # Запуск зі скрипта: той самий інтерпретатор + абсолютний шлях до app.py.
    app_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    return [sys.executable, app_py]


def build_plist_dict() -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": program_arguments(),
        "RunAtLoad": True,
        "ProcessType": "Interactive",
    }


def is_enabled() -> bool:
    return PLIST_PATH.exists()


def enable() -> None:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLIST_PATH, "wb") as fh:
        plistlib.dump(build_plist_dict(), fh)


def disable() -> None:
    try:
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                       capture_output=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        pass
    try:
        PLIST_PATH.unlink()
    except FileNotFoundError:
        pass


def toggle() -> bool:
    """Перемкнути стан. Повертає новий стан (True = увімкнено)."""
    if is_enabled():
        disable()
        return False
    enable()
    return True
