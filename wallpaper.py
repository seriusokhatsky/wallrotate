"""Встановлення шпалери робочого столу на macOS.

Два методи, які виконуються при кожній ротації:

1. AppKit (NSWorkspace.setDesktopImageURL_forScreen_options_error_) —
   основний метод. Встановлює шпалер для активного Space кожного підключеного
   екрана. Без додаткових дозволів, миттєво.

2. osascript (System Events) — резервний метод. Обходить всі десктопи через
   Apple Events; корисний, якщо AppKit недоступний (немає PyObjC).

Проблема fullscreen-просторів вирішується в app.py через підписку на
NSWorkspaceActiveSpaceDidChangeNotification: коли застосунок виходить із
fullscreen і монітор повертається до desktop-Space, шпалер ставиться повторно.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _set_via_appkit(path: str) -> bool:
    """Встановлює шпалер через NSWorkspace для всіх активних екранів."""
    try:
        from AppKit import NSWorkspace, NSScreen
        from Foundation import NSURL
    except ImportError:
        return False

    url = NSURL.fileURLWithPath_(str(path))
    workspace = NSWorkspace.sharedWorkspace()
    ok_any = False
    for screen in NSScreen.screens():
        ok, _ = workspace.setDesktopImageURL_forScreen_options_error_(
            url, screen, {}, None
        )
        ok_any = ok_any or bool(ok)
    return ok_any


def _set_via_osascript(path: str) -> bool:
    """Резервний метод: встановлює шпалер через System Events."""
    script = (
        'tell application "System Events"\n'
        '    set theDesktops to every desktop\n'
        '    repeat with aDesktop in theDesktops\n'
        f'        set picture of aDesktop to POSIX file "{path}"\n'
        '    end repeat\n'
        'end tell'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True, capture_output=True, timeout=20,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def set_wallpaper(path: str) -> bool:
    """Встановити зображення як шпалеру на всіх екранах. True якщо вдалося."""
    path = str(Path(path).expanduser())
    if _set_via_appkit(path):
        return True
    return _set_via_osascript(path)
