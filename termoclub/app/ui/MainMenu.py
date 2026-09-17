# termoclub/app/ui/MainMenu.py
"""Главное меню верхней панели: Home, Settings, Help.

Простейший вариант на `ft.MenuBar`: пункты с примером вложенного
подменю и обязательным пунктом "Exit". Класс не зависит от Flet-страницы
и терминалов — все действия отдаются наружу через колбэки.
"""
from __future__ import annotations

from collections.abc import Callable
import inspect

import flet as ft

from app.ui.FontAwesome import FontAwesome


class MainMenu:
    """Главное меню приложения (левая панель head/top)."""

    def __init__(
        self,
        on_navigate: Callable[[str], None] | None = None,
        on_new_tab: Callable[[], None] | None = None,
        on_new_window: Callable[[], None] | None = None,
        on_new_session: Callable[[], None] | None = None,
        on_new_gpu_session: Callable[[], None] | None = None,
        on_open_settings: Callable[[], None] | None = None,
        on_info: Callable[[str], None] | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        self.on_navigate = on_navigate
        self.on_new_tab = on_new_tab
        self.on_new_window = on_new_window
        self.on_new_session = on_new_session
        self.on_new_gpu_session = on_new_gpu_session
        self.on_open_settings = on_open_settings
        self.on_info = on_info
        self.on_exit = on_exit

    def _item(
        self,
        label: str,
        icon_name: str,
        action: Callable[[], None] | None,
    ) -> ft.MenuItemButton:
        async def handle_click(_: ft.ControlEvent) -> None:
            if action is not None:
                result = action()
                if inspect.isawaitable(result):
                    await result

        return ft.MenuItemButton(
            content=ft.Text(label),
            leading=FontAwesome.icon(icon_name, size=14),
            on_click=handle_click,
        )

    def build(self) -> ft.Control:
        """Возвращает MenuBar: Home | Settings | Help."""
        navigate = self.on_navigate or (lambda _route: None)
        info = self.on_info or (lambda _message: None)

        home_menu = ft.SubmenuButton(
            content=ft.Text("Home"),
            controls=[
                self._item("Dashboard", "house", lambda: navigate("/")),
                self._item("Event Log", "newspaper", lambda: navigate("/logs")),
                ft.Divider(),
                self._item(
                    "New Tab",
                    "plus",
                    (lambda: self.on_new_tab() if self.on_new_tab else None),
                ),
                self._item(
                    "New Window",
                    "open-in-new",
                    (lambda: self.on_new_window() if self.on_new_window else None),
                ),
                # Два рендерера внутреннего терминала: видно, какой открывается.
                self._item(
                    "Internal Terminal (pyte)",
                    "terminal",
                    (lambda: self.on_new_session() if self.on_new_session else None),
                ),
                self._item(
                    "Internal Terminal (smartcli-toolkit)",
                    "terminal",
                    (
                        lambda: self.on_new_gpu_session()
                        if self.on_new_gpu_session
                        else None
                    ),
                ),
                ft.Divider(),
                self._item(
                    "Exit",
                    "xmark",
                    (lambda: self.on_exit() if self.on_exit else None),
                ),
            ],
        )

        settings_menu = ft.SubmenuButton(
            content=ft.Text("Settings"),
            controls=[
                self._item(
                    "Open Settings Tab",
                    "gear",
                    (lambda: self.on_open_settings() if self.on_open_settings else None),
                ),
                ft.Divider(),
                # Настройки открываются вкладкой в рабочей области, а не
                # отдельным окном, поэтому здесь только быстрые переходы.
                ft.SubmenuButton(
                    content=ft.Text("Preferences"),
                    controls=[
                        self._item(
                            "Appearance",
                            "palette",
                            (
                                lambda: self.on_open_settings("appearance")
                                if self.on_open_settings
                                else None
                            ),
                        ),
                        self._item(
                            "Terminal",
                            "terminal",
                            (
                                lambda: self.on_open_settings("terminal-pyte")
                                if self.on_open_settings
                                else None
                            ),
                        ),
                        self._item(
                            "Plugins",
                            "puzzle-piece",
                            (
                                lambda: self.on_open_settings("plugins")
                                if self.on_open_settings
                                else None
                            ),
                        ),
                    ],
                ),
                ft.Divider(),
                self._item(
                    "About Terminals",
                    "circle-info",
                    lambda: info(
                        "Вкладки: Terminal (pyte) и Terminal (smartcli). "
                        "New Tab / New Window открывают внешний терминал "
                        "(ghostty или kitty)."
                    ),
                ),
            ],
        )

        help_menu = ft.SubmenuButton(
            content=ft.Text("Help"),
            controls=[
                self._item(
                    "Documentation",
                    "file-lines",
                    lambda: info("Documentation is not implemented yet."),
                ),
                self._item(
                    "About",
                    "circle-info",
                    lambda: info("TermoClub — terminal controller demo app."),
                ),
            ],
        )

        return ft.MenuBar(controls=[home_menu, settings_menu, help_menu])
