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
from app.ui.SessionCardData import SessionCardData
from app.ui.SessionCardList import SessionCardList
from app.ui.SystemStatuses import SystemStatuses
from app.ui.WorkspaceStage import WorkspaceStage
from app.ui.WorkspaceTabBar import WorkspaceTabBar
from app.ui.components import show_snack
from app.workspace.WorkspaceManager import WorkspaceManager
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
        self.manager = WorkspaceManager()
        self.tab_bar = WorkspaceTabBar(
            on_select=self.manager.activate,
            on_close=self.manager.close,
            on_new=self._open_terminal,
        )
        self.stage = WorkspaceStage()
        self.card_list = SessionCardList(
            on_select=self.manager.activate,
            on_close=self.manager.close,
            on_reorder=self.manager.move,
            on_new=self._open_terminal,
        )
        self.manager.subscribe(self._refresh_workspace)
        self._workspace_root = ft.Column(
            [self.tab_bar.build(), self.stage.build()],
            spacing=0,
            expand=True,
        )
        self._status_text = ft.Text("Готов", size=11)
        self._terminal_text = ft.Text("", size=12)
        self._route = HOME

    def set_status(self, message: str) -> None:
        """Обновляет нижнюю статусную панель."""
        self._status_text.value = message
        try:
            self._status_text.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.

    def exit_app(self) -> None:
        """Закрывает окно приложения (пункт меню Exit)."""
        logger.info("Exit requested from main menu")
        self.page.window.close()

    def _open_terminal(self) -> None:
        """Открывает вкладку внутреннего терминала в workspace."""
        self.manager.open("terminal", self.page)

    def _refresh_workspace(self) -> None:
        """Сверяет вкладки, сцену и карточки с состоянием менеджера."""
        datas = [
            SessionCardData.from_item(
                item, active=item.session_id == self.manager.active_id
            )
            for item in self.manager.sessions
        ]
        self.tab_bar.refresh(datas)
        self.card_list.sync(datas)
        self.stage.prune({item.session_id for item in self.manager.sessions})
        for item in self.manager.sessions:
            self.stage.mount(
                item.session_id,
                item.get_content(),
                visible=item.session_id == self.manager.active_id,
            )
        if self.manager.active_id is not None:
            self.stage.show(self.manager.active_id)

    def _setup_panels(self) -> None:
        page = self.page

        # --- Top panel: [main menu][expander][system statuses] ---
        from app.pages.home import open_new_tab, open_new_window

        menu = MainMenu(
            on_navigate=lambda route: page.push_route(route),
            on_new_tab=lambda: open_new_tab(page, self.set_status),
            on_new_window=lambda: open_new_window(page, self.set_status),
            on_new_session=self._open_terminal,
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

        # --- Left panel: session cards (filled as tabs open) ---
        self.layout.set_left_content(self.card_list.build())

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
        self._route = route
        if route == LOGS:
            from app.pages.logs import logs_content

            self.layout.set_workspace_content(logs_content(self.page))
            self.set_status("Раздел: Логи")
        else:
            self.layout.set_workspace_content(self._workspace_root)
            self.set_status("Раздел: Главная")
        logger.info("Route changed: %s", route)

    async def _bootstrap(self) -> None:
        """Отложенно открывает первую вкладку терминала."""
        self.manager.open("terminal", self.page)

    def _on_page_key(self, e: ft.KeyboardEvent) -> None:
        """Пересылает клавиши активной сессии (только маршрут workspace)."""
        if self._route != HOME:
            return
        active = self.manager.get_active()
        if active is not None and hasattr(active, "handle_key"):
            active.handle_key(e)

    def start(self) -> None:
        self.page.add(self.layout.build())
        self._setup_panels()
        self.page.on_route_change = lambda e: self.route_to_workspace(e.route)
        self.page.on_keyboard_event = self._on_page_key
        # Начальный маршрут не порождает on_route_change — рисуем явно.
        self.route_to_workspace(HOME)


async def main(page: ft.Page) -> None:
    """Настройка страницы и запуск приложения."""
    setup_logging()
    page.title = "TermoClub"
    page.theme_mode = ft.ThemeMode.DARK
    app = TermoClubApp(page)
    app.start()
    page.run_task(app._bootstrap)


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP, assets_dir=str(ASSETS_DIR))
