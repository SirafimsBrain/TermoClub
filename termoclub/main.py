# termoclub/main.py
"""TermoClub — точка входа приложения.

Главное окно: 5 панелей (верхняя, левая выезжающая, центральная
рабочая область, правая выезжающая, нижняя статусная). Компоновка
повторяет Rhizome client. Маршрутизация меняет только контент
рабочей области, каркас окна сохраняется.
"""
from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from app.layout import ApplicationLayout
from app.routes import HOME, LOGS
from app.ui.FontAwesome import FontAwesome
from app.ui.MainMenu import MainMenu
from app.ui.SystemStatuses import SystemStatuses
from app.ui.components import show_snack
from core.config import get_active_terminal_name
from logging_setup import setup_logging

logger = logging.getLogger(__name__)

#: Local Flet assets (fonts, ...). Absolute so the app works from any cwd.
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


class TermoClubApp:
    """Каркас главного окна: панели + роутинг в рабочую область."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        FontAwesome.register(page)
        self.layout = ApplicationLayout(page)
        self.statuses = SystemStatuses()
        self._status_text = ft.Text("Готов", size=11)
        self._terminal_text = ft.Text("", size=12)

    def set_status(self, message: str) -> None:
        """Обновляет нижнюю статусную панель."""
        self._status_text.value = message
        self._status_text.update()

    def exit_app(self) -> None:
        """Закрывает окно приложения (пункт меню Exit)."""
        logger.info("Exit requested from main menu")
        self.page.window.close()

    def _setup_panels(self) -> None:
        page = self.page

        # --- Top panel: [main menu][expander][system statuses] ---
        from app.pages.home import open_new_tab, open_new_window

        menu = MainMenu(
            on_navigate=lambda route: page.go(route),
            on_new_tab=lambda: open_new_tab(page, self.set_status),
            on_new_window=lambda: open_new_window(page, self.set_status),
            on_info=lambda message: show_snack(page, message),
            on_exit=self.exit_app,
        )
        menu_panel = menu.build()
        expander = ft.Container(expand=True)
        self.layout.set_top_content(
            ft.Row(
                [menu_panel, expander, self.statuses.build()],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        # --- Left panel: actions (collapsible) ---
        self.layout.set_left_content(
            ft.Column(
                [
                    ft.Text("Действия", weight=ft.FontWeight.BOLD, size=14),
                    ft.Divider(),
                    ft.FilledButton(
                        "Новая вкладка",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: open_new_tab(page, self.set_status),
                    ),
                    ft.OutlinedButton(
                        "Новое окно",
                        icon=ft.Icons.OPEN_IN_NEW,
                        on_click=lambda _: open_new_window(page, self.set_status),
                    ),
                ],
                expand=True,
            )
        )

        # --- Right panel: terminal info (collapsible) ---
        self._terminal_text.value = f"Терминал: {get_active_terminal_name()}"
        self.layout.set_right_content(
            ft.Column(
                [
                    ft.Text("Терминал", weight=ft.FontWeight.BOLD, size=14),
                    ft.Divider(),
                    self._terminal_text,
                ],
                expand=True,
            )
        )

        # --- Bottom panel: status ---
        self.layout.set_bottom_content(
            ft.Row(
                [self._status_text, ft.Container(expand=True)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

    def route_to_workspace(self, route: str) -> None:
        """Меняет только контент центральной рабочей области."""
        if route == LOGS:
            from app.pages.logs import logs_content

            self.layout.set_workspace_content(logs_content(self.page))
            self.set_status("Раздел: Логи")
        else:
            from app.pages.home import home_content

            self.layout.set_workspace_content(
                home_content(self.page, self.set_status)
            )
            self.set_status("Раздел: Главная")
        logger.info("Route changed: %s", route)

    def start(self) -> None:
        self.page.add(self.layout.build())
        self._setup_panels()
        self.page.on_route_change = lambda e: self.route_to_workspace(e.route)
        self.page.go(HOME)


async def main(page: ft.Page) -> None:
    """Настройка страницы и запуск приложения."""
    setup_logging()
    page.title = "TermoClub"
    page.theme_mode = ft.ThemeMode.DARK
    TermoClubApp(page).start()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP, assets_dir=str(ASSETS_DIR))
