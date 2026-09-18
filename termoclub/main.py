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

from app.layout import ApplicationLayout, PanelConfig
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
from core.window.WindowStateStore import WindowStateStore
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
        # Состояние окна читается до сборки каркаса: панели должны получить
        # сохранённую видимость первым же кадром, а не переключиться после.
        self.window_state = WindowStateStore()
        self.layout = ApplicationLayout(
            page,
            self._panel_config(),
            on_panel_toggle=self._on_panel_toggle,
        )
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
        self._save_window_state()
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
            # Показ вкладки включает её в раскладку, и контейнер терминала
            # сам сообщает новый размер. Запасной пересчёт по окну нужен
            # только той вкладке, которая такого события ещё не получала.
            self._fit_active_terminal()

    def _fit_active_terminal(self, width: float = 0, height: float = 0) -> None:
        """Запасной пересчёт сетки активной вкладки по размеру рабочей области.

        Основной источник размера — событие контейнера терминала: только он
        знает настоящие пиксели. Этот путь остаётся для вкладки, которая его
        ещё ни разу не получила, и по своей природе неточен (не знает про
        панель вкладок и границы), поэтому `TerminalSession.resize_to_area`
        отказывается работать, если контейнер уже сообщил размер. Иначе один
        и тот же вкладка получала бы сетку то из окна (78 строк), то из
        контейнера (74) — и терминал разъезжался.
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
        """Размер окна в пикселях через page.window (Flet >=1.0)."""
        win = getattr(self.page, "window", None)
        if win is None:
            return 0.0, 0.0
        width = float(getattr(win, "width", 0) or 0)
        height = float(getattr(win, "height", 0) or 0)
        return (width, height) if width > 0 and height > 0 else (0.0, 0.0)

    # --- Состояние главного окна ---

    def _panel_config(self) -> PanelConfig:
        """Конфигурация панелей с учётом сохранённого состояния окна.

        Умолчания (`PanelConfig`) держат панели свёрнутыми; сохранённый снимок
        может вернуть их раскрытыми. Панели получают видимость здесь, на этапе
        сборки каркаса, — тогда первый кадр уже правильный. Размер окна
        применяется отдельно, в `_restore_window_state`.
        """
        config = PanelConfig()
        state = self.window_state.state
        config.left_collapsed = not state.left_panel_open
        config.right_collapsed = not state.right_panel_open
        return config

    def _restore_window_state(self) -> None:
        """Применяет сохранённый размер окна к странице.

        Панели уже получили видимость при сборке каркаса (`_panel_config`).
        В web-режиме размер окна задаёт браузер, и `page.window` на запись
        может не влиять — это принимается как есть, состояние всё равно
        сохраняется.
        """
        state = self.window_state.state
        win = getattr(self.page, "window", None)
        if win is None:
            return
        try:
            win.width = float(state.width)
            win.height = float(state.height)
            win.maximized = state.maximized
        except (AttributeError, ValueError, TypeError) as exc:
            logger.warning("Cannot apply saved window size: %s", exc)
            return
        logger.info(
            "Window state restored: %sx%s (maximized=%s)",
            state.width,
            state.height,
            state.maximized,
        )

    def _on_panel_toggle(self, position: str, visible: bool) -> None:
        """Запоминает видимость панели в памяти, не трогая диск.

        На диск состояние уходит только при закрытии окна
        (`_save_window_state`): постоянные записи изнашивают SSD, а вид окна
        не тот случай, ради которого стоит писать на каждый клик.
        """
        field = "left_panel_open" if position == "left" else "right_panel_open"
        self.window_state.update(save=False, **{field: visible})
        logger.info("Window state: %s panel -> %s", position, visible)

    def _remember_window_size(self, width: float, height: float) -> None:
        """Запоминает размер окна в памяти, без записи файла.

        `on_resize` приходит потоком, пока пользователь тянет рамку, и каждый
        кадр даёт новую ширину: писать файл на каждое событие — лишний ввод-вывод.
        На диск размер попадает при выходе (`_save_window_state`), поэтому
        совпадение с уже сохранённым размером отсекаем, чтобы не помечать
        состояние изменённым зря.
        """
        if width <= 0 or height <= 0:
            return
        state = self.window_state.state
        new_width, new_height = int(width), int(height)
        if (new_width, new_height) == (state.width, state.height):
            return
        self.window_state.update(save=False, width=new_width, height=new_height)

    def _save_window_state(self) -> None:
        """Записывает состояние окна на диск (выход, отключение клиента).

        Здесь же подхватывается текущий размер окна: между последним
        `on_resize` и выходом он мог измениться.
        """
        size = self._page_size()
        if size != (0.0, 0.0):
            self._remember_window_size(*size)
        self.window_state.save()

    def _on_page_resize(self, event: ft.PageResizeEvent) -> None:
        """Размер окна изменился: подгоняем сетку и запоминаем размер."""
        width = float(getattr(event, "width", 0) or 0)
        height = float(getattr(event, "height", 0) or 0)
        if width <= 0 or height <= 0:
            # Событие без размеров: берём текущий размер окна как запасной путь.
            width, height = self._page_size()
        self._fit_active_terminal(width, height)
        self._remember_window_size(width, height)

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

    def _initial_route(self) -> str:
        """Маршрут, с которого стартует приложение.

        `page.route` приходит от клиента уже при создании сессии: в web это
        путь из адресной строки, в desktop — аргумент запуска. Раньше здесь
        жёстко подставлялся `HOME`, из-за чего прямой переход на `/settings`
        или `/logs` открывал главную. Незнакомый маршрут (старая ссылка,
        опечатка) сводим к главной, чтобы рабочая область не осталась пустой.
        """
        route = getattr(self.page, "route", None)
        if not isinstance(route, str) or not route:
            return HOME
        if route in (HOME, LOGS, SETTINGS):
            return route
        logger.info("Unknown initial route %r, falling back to %s", route, HOME)
        return HOME

    def start(self) -> None:
        self._restore_window_state()
        self.page.add(self.layout.build())
        self._setup_panels()
        self.page.on_route_change = lambda e: self.route_to_workspace(e.route)
        self.page.on_keyboard_event = self._on_page_key
        self.page.on_resize = self._on_page_resize
        # Последнее сохранение вида: в desktop сессия закрывается вместе с
        # окном, и `on_resize` перед этим может не прийти.
        self.page.on_disconnect = lambda e=None: self._save_window_state()
        self.page.on_close = lambda e=None: self._save_window_state()
        # Начальный маршрут не порождает on_route_change — рисуем явно.
        self.route_to_workspace(self._initial_route())


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
