"""WallRotate — menu-bar додаток, що міняє шпалери з Unsplash або Hall of FRAMED.

Запуск під час розробки:
    python3 app.py

Ключ Unsplash береться з:
    1) змінної середовища UNSPLASH_ACCESS_KEY, або
    2) поля unsplash_access_key у config.json (можна задати з меню додатку).

Джерело Hall of FRAMED не потребує ключа — дані завантажуються з публічного
JSON-репозиторію на GitHub.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

import rumps

import config as config_mod
import launch_agent
from cache import download_photo, enforce_limit
from providers.unsplash import UnsplashProvider
from providers.framedsc import FramedSCProvider, COLOR_GROUPS
from wallpaper import set_wallpaper

# Підписи інтервалів -> секунди
INTERVAL_CHOICES = [
    ("Every 15 minutes", 15 * 60),
    ("Every 30 minutes", 30 * 60),
    ("Every hour", 60 * 60),
    ("Every 3 hours", 3 * 60 * 60),
    ("Every 6 hours", 6 * 60 * 60),
]

def _resource_dir():
    """Тека ресурсів: підтримує і запуск зі скрипта, і зібраний .app (py2app).

    У зібраному .app файли з data_files лежать у Contents/Resources/.
    """
    if getattr(sys, "frozen", False):
        return os.path.normpath(
            os.path.join(os.path.dirname(sys.executable), "..", "Resources"))
    return os.path.dirname(os.path.abspath(__file__))


ASSETS_DIR = os.path.join(_resource_dir(), "assets")


def _icon_path():
    """Шлях до template-іконки menu bar.

    PDF — векторний, чіткий на retina; PNG — фолбек. Повертає None, якщо
    жодного файлу немає (тоді використаємо emoji-заголовок).
    """
    for name in ("icon.pdf", "icon.png"):
        candidate = os.path.join(ASSETS_DIR, name)
        if os.path.exists(candidate):
            return candidate
    return None


class WallRotateApp(rumps.App):
    def __init__(self):
        icon = _icon_path()
        if icon:
            # template=True -> macOS сам робить іконку чорною у світлій темі
            # і білою у темній (та підсвічує при кліку).
            super().__init__("WallRotate", icon=icon, template=True,
                             quit_button="Quit WallRotate")
        else:
            super().__init__("WallRotate", title="🖼",
                             quit_button="Quit WallRotate")
        self.config = config_mod.load_config()
        self.current_photo = None
        self._busy = False
        self._framedsc_provider: FramedSCProvider | None = None  # кешований провайдер

        self._build_menu()
        self._refresh_menu_state()

        # Таймер ротації (інтервал з конфіга)
        self.timer = rumps.Timer(self.on_tick, self.config["interval_seconds"])
        if not self.config.get("paused"):
            self.timer.start()

        # Підписуємось на зміну Space: коли застосунок виходить із fullscreen,
        # монітор повертається до desktop-Space зі своїм незалежним шпалером.
        # Observer повторно ставить поточний шпалер при кожній такій зміні.
        self._current_wallpaper_path: str | None = None
        self._register_space_observer()

        # Перша зміна одразу після старту (у фоновому потоці, щоб не блокувати UI)
        threading.Thread(target=self._change_wallpaper, daemon=True).start()

    # ---------- space-change observer ----------
    def _register_space_observer(self):
        """Підписується на NSWorkspaceActiveSpaceDidChangeNotification.

        На macOS кожен fullscreen-застосунок займає власний Space. NSWorkspace
        встановлює шпалер лише для активного Space екрана, тому desktop-Space
        може залишитись із старим шпалером. Коли користувач виходить із
        fullscreen, цей observer повторно ставить поточний шпалер — вже для
        desktop-Space, що щойно став видимим.
        """
        try:
            from AppKit import NSWorkspace

            app_ref = self

            def _on_space_change(_notification):
                path = app_ref._current_wallpaper_path
                if not path:
                    return
                def _apply():
                    time.sleep(0.3)  # чекаємо завершення анімації переходу
                    set_wallpaper(path)
                threading.Thread(target=_apply, daemon=True).start()

            NSWorkspace.sharedWorkspace().notificationCenter() \
                .addObserverForName_object_queue_usingBlock_(
                    "NSWorkspaceActiveSpaceDidChangeNotification",
                    None, None,
                    _on_space_change,
                )
        except Exception:  # noqa: BLE001
            pass  # PyObjC недоступний — observer не потрібен

    # ---------- побудова меню ----------
    def _build_menu(self):
        self.next_item = rumps.MenuItem("Next wallpaper", callback=self.on_next)
        self.pause_item = rumps.MenuItem("Pause", callback=self.on_toggle_pause)
        self.photo_item = rumps.MenuItem("No photo yet", callback=self.on_open_author)

        interval_menu = rumps.MenuItem("Interval")
        self.interval_items = []
        for label, secs in INTERVAL_CHOICES:
            item = rumps.MenuItem(label, callback=self._make_interval_cb(secs))
            self.interval_items.append((item, secs))
            interval_menu.add(item)

        # Вибір джерела зображень
        source_menu = rumps.MenuItem("Source")
        self.source_unsplash_item = rumps.MenuItem(
            "Unsplash", callback=self._make_source_cb("unsplash"))
        self.source_framedsc_item = rumps.MenuItem(
            "Hall of FRAMED", callback=self._make_source_cb("framedsc"))
        source_menu.add(self.source_unsplash_item)
        source_menu.add(self.source_framedsc_item)

        self.theme_item = rumps.MenuItem("Set theme…", callback=self.on_set_theme)
        self.key_item = rumps.MenuItem("Set Unsplash API key…", callback=self.on_set_key)
        self.login_item = rumps.MenuItem("Launch at login", callback=self.on_toggle_login)
        about_item = rumps.MenuItem("About", callback=self.on_about)

        # --- Hall of FRAMED filters submenu ---
        hof_menu = rumps.MenuItem("Hall of FRAMED filters")

        # Score
        score_menu = rumps.MenuItem("Min score")
        self.score_items: list[tuple[rumps.MenuItem, int]] = []
        for label, val in [("Any", 0), ("≥ 5", 5), ("≥ 10", 10), ("≥ 25", 25), ("≥ 50", 50)]:
            item = rumps.MenuItem(label, callback=self._make_score_cb(val))
            self.score_items.append((item, val))
            score_menu.add(item)

        # Color group
        color_menu = rumps.MenuItem("Color")
        self.color_items: list[tuple[rumps.MenuItem, str | None]] = []
        any_color = rumps.MenuItem("Any", callback=self._make_color_cb(None))
        self.color_items.append((any_color, None))
        color_menu.add(any_color)
        for group_name in COLOR_GROUPS:
            item = rumps.MenuItem(group_name, callback=self._make_color_cb(group_name))
            self.color_items.append((item, group_name))
            color_menu.add(item)

        # Game filters
        self.include_games_item = rumps.MenuItem(
            "Include games…", callback=self.on_framedsc_include_games)
        self.exclude_games_item = rumps.MenuItem(
            "Exclude games…", callback=self.on_framedsc_exclude_games)

        # Stats (тільки текст, без колбеку)
        self.framedsc_stats_item = rumps.MenuItem("–")

        hof_menu.add(score_menu)
        hof_menu.add(color_menu)
        hof_menu.add(self.include_games_item)
        hof_menu.add(self.exclude_games_item)
        hof_menu.add(None)
        hof_menu.add(self.framedsc_stats_item)

        self.menu = [
            self.photo_item,
            None,  # роздільник
            self.next_item,
            self.pause_item,
            interval_menu,
            None,
            source_menu,
            self.theme_item,
            self.key_item,
            None,
            hof_menu,
            self.login_item,
            None,
            about_item,
        ]

    def _make_interval_cb(self, secs):
        def cb(_sender):
            self.config["interval_seconds"] = secs
            config_mod.save_config(self.config)
            # Зупиняємо ПЕРЕД зміною інтервалу: сеттер rumps.Timer.interval
            # ігнорує нове значення, якщо таймер активний і поточний цикл
            # ще не завершився. Після stop() _status=False — сеттер просто
            # записує _interval, а start() підхопить нове значення.
            self.timer.stop()
            self.timer.interval = secs
            if not self.config.get("paused"):
                self.timer.start()
            self._refresh_menu_state()
            rumps.notification("WallRotate", "Interval updated",
                               self._interval_label(secs))
        return cb

    def _make_score_cb(self, val: int):
        def cb(_sender):
            self.config["framedsc_min_score"] = val
            config_mod.save_config(self.config)
            self._apply_framedsc_filters()
            self._refresh_menu_state()
        return cb

    def _make_color_cb(self, group: str | None):
        def cb(_sender):
            self.config["framedsc_color_group"] = group or ""
            config_mod.save_config(self.config)
            self._apply_framedsc_filters()
            self._refresh_menu_state()
        return cb

    def on_framedsc_include_games(self, _sender):
        current = self.config.get("framedsc_include_games", "")
        window = rumps.Window(
            title="Include games",
            message=(
                "Show only shots from these games.\n"
                "Comma-separated, case-insensitive partial match.\n"
                "Leave empty to include all games."
            ),
            default_text=current,
            ok="Save", cancel="Cancel", dimensions=(360, 24),
        )
        resp = window.run()
        if resp.clicked:
            self.config["framedsc_include_games"] = resp.text.strip()
            config_mod.save_config(self.config)
            self._apply_framedsc_filters()
            self._refresh_menu_state()

    def on_framedsc_exclude_games(self, _sender):
        current = self.config.get("framedsc_exclude_games", "")
        window = rumps.Window(
            title="Exclude games",
            message=(
                "Hide shots from these games.\n"
                "Comma-separated, case-insensitive partial match.\n"
                "Leave empty to exclude nothing."
            ),
            default_text=current,
            ok="Save", cancel="Cancel", dimensions=(360, 24),
        )
        resp = window.run()
        if resp.clicked:
            self.config["framedsc_exclude_games"] = resp.text.strip()
            config_mod.save_config(self.config)
            self._apply_framedsc_filters()
            self._refresh_menu_state()

    def _make_source_cb(self, provider_name: str):
        def cb(_sender):
            self.config["provider"] = provider_name
            config_mod.save_config(self.config)
            self._refresh_menu_state()
            label = "Unsplash" if provider_name == "unsplash" else "Hall of FRAMED"
            rumps.notification("WallRotate", "Source changed", label)
            threading.Thread(target=self._change_wallpaper, daemon=True).start()
        return cb

    # ---------- стан меню ----------
    @staticmethod
    def _interval_label(secs):
        for label, s in INTERVAL_CHOICES:
            if s == secs:
                return label
        return f"Every {secs // 60} min"

    def _refresh_menu_state(self):
        paused = self.config.get("paused", False)
        self.pause_item.title = "Resume" if paused else "Pause"

        # позначка ✓ навпроти активного інтервалу
        active = self.config["interval_seconds"]
        for item, secs in self.interval_items:
            item.state = 1 if secs == active else 0

        # позначка ✓ навпроти активного джерела
        provider = self.config.get("provider", "unsplash")
        self.source_unsplash_item.state = 1 if provider == "unsplash" else 0
        self.source_framedsc_item.state = 1 if provider == "framedsc" else 0

        # Unsplash-специфічні пункти — показуємо тільки якщо обрано Unsplash
        is_unsplash = (provider == "unsplash")
        self.theme_item.set_callback(self.on_set_theme if is_unsplash else None)
        self.key_item.set_callback(self.on_set_key if is_unsplash else None)
        self.theme_item.title = "Set theme…" if is_unsplash else "Set theme… (Unsplash only)"
        self.key_item.title = (
            "Set Unsplash API key…" if is_unsplash else "Set Unsplash API key… (inactive)"
        )

        # --- FRAMED filters state ---
        is_framedsc = (provider == "framedsc")
        min_score = self.config.get("framedsc_min_score", 0)
        for item, val in self.score_items:
            item.state = 1 if val == min_score else 0

        color_group = self.config.get("framedsc_color_group") or None
        for item, group in self.color_items:
            item.state = 1 if group == color_group else 0

        inc = self.config.get("framedsc_include_games", "").strip()
        exc = self.config.get("framedsc_exclude_games", "").strip()
        self.include_games_item.title = (f"Include: {inc}" if inc else "Include games…")
        self.exclude_games_item.title = (f"Exclude: {exc}" if exc else "Exclude games…")

        # Активуємо фільтри лише для framedsc
        for item in [self.include_games_item, self.exclude_games_item]:
            item.set_callback(
                (self.on_framedsc_include_games
                 if item is self.include_games_item
                 else self.on_framedsc_exclude_games)
                if is_framedsc else None
            )

        # позначка ✓ для автозапуску при вході
        self.login_item.state = 1 if launch_agent.is_enabled() else 0

    # ---------- ключ та провайдер ----------
    def _get_unsplash_key(self):
        return os.environ.get("UNSPLASH_ACCESS_KEY") or self.config.get("unsplash_access_key", "")

    def _framedsc_filter_kwargs(self) -> dict:
        inc = [g for g in self.config.get("framedsc_include_games", "").split(",") if g.strip()]
        exc = [g for g in self.config.get("framedsc_exclude_games", "").split(",") if g.strip()]
        return dict(
            min_score=self.config.get("framedsc_min_score", 0),
            include_games=inc,
            exclude_games=exc,
            color_group=self.config.get("framedsc_color_group") or None,
        )

    def _build_provider(self):
        provider_name = self.config.get("provider", "unsplash")
        if provider_name == "framedsc":
            if self._framedsc_provider is None:
                self._framedsc_provider = FramedSCProvider(**self._framedsc_filter_kwargs())
            return self._framedsc_provider
        # Unsplash
        key = self._get_unsplash_key()
        if not key:
            return None
        return UnsplashProvider(key, app_name=config_mod.APP_NAME)

    def _apply_framedsc_filters(self) -> None:
        """Оновити фільтри провайдера (без перезавантаження даних) і stats."""
        if self._framedsc_provider is None:
            return
        self._framedsc_provider.update_filters(**self._framedsc_filter_kwargs())
        self._update_framedsc_stats()

    def _update_framedsc_stats(self) -> None:
        if self._framedsc_provider and self._framedsc_provider.shot_count > 0:
            self.framedsc_stats_item.title = f"📊 {self._framedsc_provider.shot_count} shots match"
        elif self._framedsc_provider:
            self.framedsc_stats_item.title = "⚠️ 0 shots — relax filters"
        else:
            self.framedsc_stats_item.title = "–"

    # ---------- основна дія ----------
    def on_tick(self, _timer):
        threading.Thread(target=self._change_wallpaper, daemon=True).start()

    def on_next(self, _sender):
        threading.Thread(target=self._change_wallpaper, daemon=True).start()

    def _change_wallpaper(self):
        if self._busy:
            return
        self._busy = True
        try:
            provider = self._build_provider()
            if provider is None:
                # Може бути None тільки для Unsplash без ключа
                rumps.notification(
                    "WallRotate", "API key needed",
                    "Set your Unsplash API key from the menu.")
                self.photo_item.title = "⚠️ Set Unsplash API key"
                return

            photo = provider.get_random(
                query=self.config.get("query"),
                orientation=self.config.get("orientation", "landscape"),
            )
            path = download_photo(photo, config_mod.CACHE_DIR)
            ok = set_wallpaper(str(path))
            if ok:
                self._current_wallpaper_path = str(path)  # для space-observer
                provider.on_applied(photo)  # тригер download-endpoint (Unsplash)
                enforce_limit(config_mod.CACHE_DIR, self.config.get("cache_limit", 20))
                self.current_photo = photo
                # Оновлюємо stats після першого завантаження даних
                if photo.source == "framedsc":
                    self._update_framedsc_stats()
                # Показуємо назву гри для FramedSC, автора для Unsplash
                if photo.source == "framedsc" and photo.description:
                    self.photo_item.title = f"🎮 {photo.description} · {photo.author_name}"
                else:
                    self.photo_item.title = f"📷 {photo.author_name}"
            else:
                self.photo_item.title = "⚠️ Could not set wallpaper"
        except Exception as exc:  # noqa: BLE001 — для MVP показуємо помилку в меню
            self.photo_item.title = f"⚠️ {type(exc).__name__}"
            rumps.notification("WallRotate", "Error", str(exc)[:200])
        finally:
            self._busy = False

    # ---------- пункти меню ----------
    def on_toggle_pause(self, _sender):
        paused = not self.config.get("paused", False)
        self.config["paused"] = paused
        config_mod.save_config(self.config)
        if paused:
            self.timer.stop()
        else:
            self.timer.start()
        self._refresh_menu_state()

    def on_toggle_login(self, _sender):
        enabled = launch_agent.toggle()
        self._refresh_menu_state()
        if enabled:
            msg = "WallRotate will start automatically at next login."
        else:
            msg = "WallRotate will no longer start at login."
        rumps.notification("WallRotate", "Launch at login", msg)

    def on_open_author(self, _sender):
        if self.current_photo:
            link = self.current_photo.author_link
            # Для Unsplash додаємо UTM-параметри
            if self.current_photo.source == "unsplash":
                provider = self._build_provider()
                if provider:
                    link = provider.attribution_url(link)
            webbrowser.open(link)

    def on_set_theme(self, _sender):
        window = rumps.Window(
            title="Wallpaper theme",
            message="Keywords (comma-separated), e.g. nature, mountains, ocean",
            default_text=self.config.get("query", ""),
            ok="Save", cancel="Cancel", dimensions=(320, 24),
        )
        resp = window.run()
        if resp.clicked:
            self.config["query"] = resp.text.strip()
            config_mod.save_config(self.config)
            rumps.notification("WallRotate", "Theme updated", self.config["query"] or "(any)")

    def on_set_key(self, _sender):
        window = rumps.Window(
            title="Unsplash API key",
            message="Paste your Unsplash Access Key (unsplash.com/developers)",
            default_text=self.config.get("unsplash_access_key", ""),
            ok="Save", cancel="Cancel", dimensions=(360, 24),
        )
        resp = window.run()
        if resp.clicked:
            self.config["unsplash_access_key"] = resp.text.strip()
            config_mod.save_config(self.config)
            rumps.notification("WallRotate", "API key saved", "Fetching a wallpaper…")
            threading.Thread(target=self._change_wallpaper, daemon=True).start()

    def on_about(self, _sender):
        rumps.alert(
            title="WallRotate",
            message=(
                "Auto-rotating desktop wallpapers.\n\n"
                "Sources:\n"
                "• Unsplash — photos via the Unsplash API\n"
                "• Hall of FRAMED — curated game screenshots\n"
                "  (framedsc.com)\n\n"
                "MVP build."
            ),
        )


if __name__ == "__main__":
    WallRotateApp().run()
