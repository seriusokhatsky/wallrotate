"""Пакування у standalone .app через py2app (етап 4, опційно).

Збірка:
    pip install py2app
    python3 setup.py py2app

Результат — dist/WallRotate.app. LSUIElement=True робить його фоновим
(без іконки в Dock). Для роздачі іншим знадобиться підпис + нотаризація.
"""
from setuptools import setup

APP = ["app.py"]
# Іконки потрапляють у Contents/Resources/assets/ всередині .app
DATA_FILES = [("assets", ["assets/icon.pdf", "assets/icon.png", "assets/icon.svg"])]
OPTIONS = {
    "argv_emulation": False,
    "packages": ["rumps", "requests", "certifi"],
    "plist": {
        "LSUIElement": True,                 # фоновий застосунок, без Dock
        "CFBundleName": "WallRotate",
        "CFBundleDisplayName": "WallRotate",
        "CFBundleIdentifier": "com.example.wallrotate",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
    },
}

setup(
    app=APP,
    name="WallRotate",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
