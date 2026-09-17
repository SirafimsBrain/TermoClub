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
from app.routes import HOME, LOGS, SETTINGS
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
from core.settings.SettingsApplier import SettingsApplier
from core.settings.SettingsStore import SettingsStore
from core.terminal.factory import create_terminal_controller
from logging_setup import setup_logging

logger = logging.getLogger(__name__)

#: Local Flet assets (fonts, ...). Absolute so the app works from any cwd.
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

#: Рендерер -> заголовок вкладки: в UI сразу видно, какой терминал открыт.
#: Оба варианта — чистый Python: `terminal` рисует pyte + Flet, `terminal-gpu`
#: берёт PTY и эмуляцию экрана из smartcli-toolkit. Оба работают в
#: stock-клиенте (`flet run`), без Dart-расширений и Flutter SDK.
TERMINAL_TITLES = {
    "terminal": "Terminal (pyte)",
    "terminal-gpu": "Terminal (smartcli)",
}

#: Рендерер -> категория настроек, описывающая его внешний вид.
TERMINAL_SETTINGS = {
    "terminal": "terminal-pyte",
    "terminal-gpu": "terminal-smartcli",
}


class TermoClubApp:
    """Каркас главного окна: панели + роутинг в рабочую область."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        FontAwesome.register(page)
        self.layout = ApplicationLayout(page)
        self.statuses = SystemStatuses()
        self.manager = WorkspaceManager()
        # Настройки: одно хранилище на приложение, поверх — применение к
        # живым вкладкам и странице (тема, шрифт терминала, частота отрисовки).
        self.settings = SettingsStore()
        self.applier = SettingsApplier(
            self.settings,
            sessions=lambda: self.manager.sessions,
            page=page,
            terminal_factory=create_terminal_controller,
        )
        self.settings.subscribe_changes(self.applier.apply_key)
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
            # STRETCH даёт сцене тугую ширину: иначе стек сцены сжимается
            # по содержимому и терминал не может занять всю область.
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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

    def _open_terminal(self, kind: str = "terminal") -> None:
        """Открывает вкладку внутреннего терминала выбранного рендерера.

        Сессия собирает движок в конструкторе, поэтому сбой (не установлен
        smartcli-toolkit, платформа без PTY) приходит сюда с готовым текстом:
        показываем его в статусной панели и снекбаром вместо пустой вкладки.
        """
        title = TERMINAL_TITLES.get(kind, kind)
        kwargs: dict = {"title": title}
        terminal_slug = TERMINAL_SETTINGS.get(kind)
        if terminal_slug is not None and self.settings.schema.find(terminal_slug) is not None:
            kwargs["appearance"] = self.settings.values(terminal_slug)
        try:
            self.manager.open(kind, self.page, **kwargs)
        except Exception as exc:  # noqa: BLE001 — пользователю нужен любой текст
            logger.exception("Failed to open %s session", kind)
            message = f"Не удалось открыть «{title}»: {exc}"
            self.set_status(message)
            show_snack(self.page, message, is_error=True)

    def _open_settings(self, slug: str | None = None) -> None:
        """Открывает вкладку Settings (и, при необходимости, её категорию).

        Вкладка одна: повторный вызов только активирует её и переключает
        категорию, чтобы не плодить дубликаты в рабочей области.
        """
        session = self._find_settings_session()
        if session is None:
            try:
                session = self.manager.open("settings", self.page, store=self.settings)
            except Exception as exc:  # noqa: BLE001 — пользователю нужен текст
                logger.exception("Failed to open settings session")
                message = f"Не удалось открыть настройки: {exc}"
                self.set_status(message)
                show_snack(self.page, message, is_error=True)
                return
        else:
            self.manager.activate(session.session_id)
        if slug:
            try:
                session.get_content()  # гарантирует, что экран уже собран
                if session.view is not None:
                    session.view.select(slug)
            except Exception:  # noqa: BLE001 — категория не должна ломать вкладку
                logger.exception("Failed to select settings category %r", slug)
        self.set_status("Настройки")

    def _find_settings_session(self):
        """Находит уже открытую вкладку Settings (если есть)."""
        for item in self.manager.sessions:
            if item.kind == "settings":
                return item
        return None

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
            # Скрытая вкладка о своём размере не сообщает, поэтому сетку
            # показываемой считаем из размера окна: иначе после переключения
            # вкладок терминал остался бы с прежним (или начальным) размером.
            self._fit_active_terminal()

    def _fit_active_terminal(self, width: float = 0, height: float = 0) -> None:
        """Пересчитывает сетку активной вкладки под размер рабочей области.

        Вызывается по `page.on_resize` (размер страницы меняется раньше, чем
        приходит событие контейнера, а для только что показанной вкладки оно
        может не прийти вовсе) и при показе вкладки.
        """
        active = self.manager.get_active()
        if active is None or not hasattr(active, "resize_to_area"):
            return
        if width <= 0 or height <= 0:
            width, height = self._page_size()
        if width <= 0 or height <= 0:
            return
        area_width, area_height = self.layout.workspace_area_size(width, height)
        active.resize_to_area(area_width, area_height)

    def _page_size(self) -> tuple[float, float]:
        """Размер окна в пикселях: сама страница, иначе её окно.

        `page.width`/`page.height` есть и в 0.86, и в 1.0 (там они уже
        помечены устаревшими в пользу `page.window`), поэтому смотрим оба
        источника — иначе после обновления Flet вкладка осталась бы без
        пересчёта размера.
        """
        sources = (self.page, getattr(self.page, "window", None))
        for source in sources:
            if source is None:
                continue
            width = float(getattr(source, "width", 0) or 0)
            height = float(getattr(source, "height", 0) or 0)
            if width > 0 and height > 0:
                return width, height
        return 0.0, 0.0

    def _on_page_resize(self, event: ft.PageResizeEvent) -> None:
        """Размер окна изменился: подгоняем сетку активного терминала."""
        self._fit_active_terminal(
            float(getattr(event, "width", 0) or 0),
            float(getattr(event, "height", 0) or 0),
        )

    def _setup_panels(self) -> None:
        page = self.page

        # --- Top panel: [main menu][expander][system statuses] ---
        from app.pages.home import open_new_tab, open_new_window

        menu = MainMenu(
            on_navigate=lambda route: page.push_route(route),
            on_new_tab=lambda: open_new_tab(page, self.set_status),
            on_new_window=lambda: open_new_window(page, self.set_status),
            on_new_session=lambda: self._open_terminal("terminal"),
            on_new_gpu_session=lambda: self._open_terminal("terminal-gpu"),
            on_open_settings=self._open_settings,
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
        # Внутри вкладок работают два своих рендерера; `ghostty`/`kitty` —
        # внешние терминалы, которые открывают пункты New Tab/New Window.
        # Раньше панель показывала только внешний и путала пользователя.
        self._terminal_text.value = (
            "Вкладки: " + ", ".join(TERMINAL_TITLES.values())
        )
        self.layout.set_right_content(
            ft.Column(
                [
                    ft.Text("Терминал", weight=ft.FontWeight.BOLD, size=14),
                    ft.Divider(),
                    self._terminal_text,
                    ft.Text(
                        f"Новая вкладка/окно: {get_active_terminal_name()}", size=12
                    ),
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
        elif route == SETTINGS:
            # Настройки — обычная вкладка workspace, поэтому маршрут лишь
            # показывает рабочую область и открывает (или активирует) её.
            self.layout.set_workspace_content(self._workspace_root)
            self._open_settings()
        else:
            self.layout.set_workspace_content(self._workspace_root)
            self.set_status("Раздел: Главная")
            # Возврат из логов подменяет контент рабочей области: контрол
            # терминала снова оказывается в дереве, но фокус уже потерян, а
            # без него не вводится кириллица.
            active = self.manager.get_active()
            if active is not None and hasattr(active, "focus_input"):
                active.focus_input()
            self._fit_active_terminal()
        logger.info("Route changed: %s", route)

    async def _bootstrap(self) -> None:
        """Восстанавливает сессии запуска и применяет стартовые настройки."""
        self.applier.apply_all()
        self._scan_plugins()
        kind = self.settings.get("global", "startup_session")
        if kind and kind != "none":
            self._open_terminal(kind)

    def _scan_plugins(self) -> None:
        """Подхватывает настройки плагинов из профиля при старте.

        Сканирование включается настройками `plugins`, поэтому выключенные
        плагины или отключённый автообзор не мешают запуску приложения.
        """
        schema = self.settings.schema.find("plugins")
        if schema is None:
            return
        if not self.settings.get("plugins", "enable_plugins"):
            logger.info("Plugin scan skipped: plugins are disabled")
            return
        if not self.settings.get("plugins", "auto_discover"):
            logger.info("Plugin scan skipped: auto discover is off")
            return
        try:
            found = self.settings.refresh_plugins()
        except Exception:  # noqa: BLE001 — плагин не должен ронять запуск
            logger.exception("Plugin scan failed at startup")
            return
        logger.info("Plugin scan at startup: %d plugin(s) found", len(found))

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
        self.page.on_resize = self._on_page_resize
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
