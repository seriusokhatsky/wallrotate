"""Встановлення шпалери робочого столу на macOS.

Основний шлях — нативний AppKit (NSWorkspace) через PyObjC: працює всередині
нашого процесу і не потребує дозволу на Automation (на відміну від AppleScript
через Finder). Якщо PyObjC недоступний — фолбек на osascript.

Зауваження про Spaces: macOS зберігає шпалеру окремо для кожного робочого
простору (Space). Цей виклик змінює фон активного Space кожного екрана.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _set_via_appkit(path: str) -> bool:
    try:
        from AppKit import NSWorkspace, NSScreen
        from Foundation import NSURL
    except ImportError:
        return False

    url = NSURL.fileURLWithPath_(str(path))
    workspace = NSWorkspace.sharedWorkspace()
    ok_any = False
    for screen in NSScreen.screens():
        ok, _err = workspace.setDesktopImageURL_forScreen_options_error_(
            url, screen, {}, None
        )
        ok_any = ok_any or bool(ok)
    return ok_any


def _set_via_osascript(path: str) -> bool:
    script = (
        'tell application "System Events" to set picture of every '
        f'desktop to POSIX file "{path}"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=True,
                       capture_output=True, timeout=20)
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def set_wallpaper(path: str) -> bool:
    """Встановити зображення як шпалеру на всіх екранах. True якщо вдалося."""
    path = str(Path(path).expanduser())
    if _set_via_appkit(path):
        return True
    return _set_via_osascript(path)
