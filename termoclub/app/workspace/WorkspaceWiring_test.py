# termoclub/app/workspace/WorkspaceWiring_test.py
"""Сквозной тест связки менеджер -> вкладки/сцена/карточки (без страницы)."""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import flet as ft
import pytest

from main import TermoClubApp


class _StubPage:
    def __init__(self, route: str = "/") -> None:
        self.fonts: dict | None = None
        self.added: list = []
        self.route = route
        self.window = SimpleNamespace(width=1200, height=800)

    def add(self, *controls) -> None:  # type: ignore[no-untyped-def]
        self.added.extend(controls)

    def update(self) -> None:
        pass

    def go(self, route: str) -> None:
        pass

    def run_task(self, handler, *args):  # type: ignore[no-untyped-def]
        return asyncio.ensure_future(handler(*args))


def _tabs(app: TermoClubApp) -> list:
    return [c for c in app.tab_bar._row.controls if isinstance(c, ft.Container)]


@pytest.fixture(autouse=True)
def _isolated_profile(tmp_path, monkeypatch):
    """Уводит профиль приложения в tmp: тесты не трогают `~/.termoclub`.

    `TermoClubApp` создаёт хранилище настроек от профиля по умолчанию,
    поэтому корень подменяется до сборки приложения.
    """
    from core.storage.backends.ProfileBackend import ProfileBackend

    monkeypatch.setattr(ProfileBackend, "default", classmethod(lambda cls: cls(tmp_path)))
    return tmp_path


def _rendered(item) -> str:  # type: ignore[no-untyped-def]
    """Собирает текст, который реально уходит в спаны экрана терминала."""
    return "".join(span.text or "" for span in item._view._text.spans)


def test_both_terminal_renderers_open_in_tabs() -> None:
    """В workspace открываются оба терминала: pyte и smartcli-toolkit.

    Рендереры должны быть вызываемыми по отдельности — иначе непонятно,
    какой терминал открывает кнопка.
    """
    page = _StubPage()
    app = TermoClubApp(page)  # type: ignore[arg-type]
    pyte = app.manager.open("terminal", title="Terminal (pyte)")
    gpu = app.manager.open("terminal-gpu", title="Terminal (smartcli)")
    app._refresh_workspace()

    assert [i.title for i in app.manager.sessions] == [
        "Terminal (pyte)",
        "Terminal (smartcli)",
    ]
    assert [i.kind for i in app.manager.sessions] == ["terminal", "terminal-gpu"]
    assert len(_tabs(app)) == 2
    assert len(app.stage._stack.controls) == 2
    # Контент живёт в сцене, а не в корне страницы: иначе в окне появляется
    # вторая панель рядом с ApplicationLayout.
    assert page.added == []

    app.manager.close(gpu.session_id)
    app.manager.close(pyte.session_id)
    assert app.manager.sessions == []


def test_first_prompt_is_rendered_as_a_full_grid() -> None:
    """Шелл отвечает, и его вывод влезает во вьюпорт по строкам.

    Раньше экран прокручивался к низу и показывал только пустые строки —
    ни приглашения, ни места для ввода.
    """
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        page = _StubPage()
        app = TermoClubApp(page)  # type: ignore[arg-type]
        app.start()
        item = app.manager.open("terminal", page)  # type: ignore[arg-type]
        await asyncio.wait_for(_wait_running(item), timeout=10)
        await asyncio.wait_for(_wait_marker(item), timeout=10)

        rendered = _rendered(item)
        assert MARKER in rendered
        # Строк ровно столько, сколько в сетке: лишние уехали бы в скролл.
        assert rendered.count("\n") == item._screen.lines - 1
        app.manager.close(item.session_id)

    asyncio.run(scenario())


#: Слово, которое шелл печатает только в выводе (см. `_wait_marker`).
MARKER = "TERMOCLUB_READY"


async def _wait_marker(item, marker: str = MARKER) -> None:  # type: ignore[no-untyped-def]
    """Ждёт маркер вывода шелла, не завязываясь на его `PS1`.

    Приглашение зависит от конфигурации пользователя (zsh рисует `➜`), поэтому
    проверяем не `#`/`$`, а ответ на команду. Слово собирается из двух частей
    (`TERMO""CLUB_READY`): в эхе самого ввода оно тогда не встречается, а шелл
    печатает его только в выводе — ждать приходится именно отрисовку.
    """
    item._bridge.write(f'echo {marker[:5]}""{marker[5:]}\r'.encode())
    while marker not in _rendered(item):
        await asyncio.sleep(0.02)


def test_open_syncs_tabs_stage_cards() -> None:
    """Открытие сессии отражается во вкладках, сцене и карточках."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    first = app.manager.open("editor", title="readme")
    second = app.manager.open("terminal", title="ops")
    app._refresh_workspace()

    assert len(_tabs(app)) == 2
    assert len(app.card_list._list.controls) == 2
    assert len(app.stage._stack.controls) == 2
    assert app.stage._mounted[second.session_id].visible is True
    assert app.stage._mounted[first.session_id].visible is False

    app.manager.close(second.session_id)
    app._refresh_workspace()
    assert len(_tabs(app)) == 1
    assert len(app.card_list._list.controls) == 1
    assert len(app.stage._stack.controls) == 1


def _key(key: str, **mods) -> ft.KeyboardEvent:
    return ft.KeyboardEvent(
        name="keyboard_event",
        key=key,
        shift=mods.get("shift", False),
        ctrl=mods.get("ctrl", False),
        alt=mods.get("alt", False),
        meta=mods.get("meta", False),
        control=None,  # type: ignore[arg-type]
    )


def _change(value: str):  # type: ignore[no-untyped-def]
    """Мок события on_change скрытого поля ввода."""
    return SimpleNamespace(control=SimpleNamespace(value=value))


def test_text_input_roundtrip() -> None:
    """Ввод: скрытое поле -> PTY (cat) -> pump -> текст экрана.

    Печатаемые символы идут через IME-поле `TerminalView`, а не через
    диспетчер `page.on_keyboard_event`: тот отдаёт только логические метки
    клавиш (латиница в верхнем регистре без раскладки).
    """
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        page = _StubPage()
        app = TermoClubApp(page)  # type: ignore[arg-type]
        app.start()
        item = app.manager.open("terminal", page, shell="/bin/cat", args=[])  # type: ignore[arg-type]
        await asyncio.wait_for(_wait_running(item), timeout=10)
        item._view._on_field_focus(None)  # autofocus скрытого поля
        item._view._on_field_change(_change("привет"))
        await asyncio.wait_for(_wait_text(item, "привет"), timeout=10)
        assert "привет" in item.display_text
        # Экран обновляется по троттлингу (хвостовой отрисовкой) — ждём её.
        await asyncio.wait_for(_wait_rendered(item, "привет"), timeout=10)
        # Диспетчер молчит: символы не дублируются.
        app._on_page_key(_key("a"))
        assert item.display_text.count("привет") == 1
        app.manager.close(item.session_id)

    asyncio.run(scenario())


async def _wait_running(item) -> None:  # type: ignore[no-untyped-def]
    while not item._bridge.running:
        await asyncio.sleep(0.02)


def test_smartcli_terminal_renders_in_the_tab() -> None:
    """smartcli-вкладка: приглашение и кириллица доезжают до отрисовки.

    Раньше сессия слала на `page.add()` свой контрол (вторая панель в окне) и
    ни разу не вызывала отрисовку, поэтому вкладка оставалась чёрной, а
    smartcli-API вызывался как асинхронный (`await start()`, `async for pump()`) —
    запуск падал с TypeError.
    """
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        page = _StubPage()
        app = TermoClubApp(page)  # type: ignore[arg-type]
        app.start()
        item = app.manager.open("terminal-gpu", page, shell="/bin/cat", args=[])  # type: ignore[arg-type]
        await asyncio.wait_for(_wait_running(item), timeout=10)
        item._view._on_field_focus(None)  # autofocus скрытого поля
        item._view._on_field_change(_change("привет"))
        await asyncio.wait_for(_wait_rendered(item, "привет"), timeout=10)
        assert "привет" in item.display_text
        # Панелей ровно две: каркас приложения и рабочая область внутри него.
        assert len(page.added) == 1
        app.manager.close(item.session_id)

    asyncio.run(scenario())


async def _wait_text(item, needle: str) -> None:  # type: ignore[no-untyped-def]
    while needle not in item.display_text:
        await asyncio.sleep(0.02)


async def _wait_rendered(item, needle: str) -> None:  # type: ignore[no-untyped-def]
    while needle not in _rendered(item):
        await asyncio.sleep(0.02)


def test_focus_is_requested_for_a_newly_mounted_tab() -> None:
    """Смонтированная вкладка сама возвращает себе фокус поля ввода.

    Иначе вторая открытая вкладка оставалась без фокуса, то есть без ввода
    кириллицы: `on_focus()` вызывается до того, как контрол попал в дерево.
    """
    async def scenario() -> None:
        page = _StubPage()
        app = TermoClubApp(page)  # type: ignore[arg-type]
        app.start()
        app.manager.open("terminal", page, title="pane 1")  # type: ignore[arg-type]
        second = app.manager.open("terminal", page, title="pane 2")  # type: ignore[arg-type]
        focused: list[bool] = []

        async def fake_focus() -> None:
            focused.append(True)

        second._view.focus_input = fake_focus  # type: ignore[method-assign]
        app._refresh_workspace()  # монтирует контент вкладки
        await asyncio.sleep(0.1)
        assert focused
        for item in app.manager.sessions:
            app.manager.close(item.session_id)

    asyncio.run(scenario())


def test_resize_of_the_window_refits_the_active_tab() -> None:
    """Размер окна пересчитывает сетку активной вкладки.

    Скрытая вкладка событий о размере не получает, а при показе новый кадр
    контейнера может не прийти: без пересчёта из размера окна после
    переключения вкладок терминал оставался бы с прежней сеткой.
    """
    page = _StubPage()
    app = TermoClubApp(page)  # type: ignore[arg-type]
    item = app.manager.open("terminal", title="pyte")
    area = app.layout.workspace_area_size(1400, 900)
    app._on_page_resize(SimpleNamespace(width=1400, height=900))
    assert (item._screen.columns, item._screen.lines) == item._view.grid_size(*area)
    assert item._view.grid_size(*area) != (80, 24)

    # Показ вкладки тоже пересчитывает сетку: без явного события о размере
    # берём его у самой страницы.
    page.window.width, page.window.height = 900, 600
    small_area = app.layout.workspace_area_size(900, 600)
    app._fit_active_terminal()
    assert (item._screen.columns, item._screen.lines) == item._view.grid_size(
        *small_area
    )
def test_settings_menu_opens_a_single_workspace_tab() -> None:
    """Settings из главного меню — обычная вкладка workspace, и она одна.

    Повторный выбор раздела не плодит дубликаты: вкладка активируется, а
    выбранная категория переключается в уже открытом экране.
    """
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()

    app._open_settings()
    app._refresh_workspace()
    assert [item.kind for item in app.manager.sessions] == ["settings"]
    assert len(_tabs(app)) == 1

    app._open_settings("terminal-pyte")
    app._refresh_workspace()
    assert len(app.manager.sessions) == 1
    session = app.manager.get_active()
    assert session is not None and session.kind == "settings"
    assert session.view is not None and session.view.panel.slug == "terminal-pyte"


def test_settings_route_maps_to_the_settings_tab() -> None:
    """Маршрут `/settings` открывает ту же вкладку, что и пункт меню."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()

    app.route_to_workspace("/settings")
    assert [item.kind for item in app.manager.sessions] == ["settings"]
    assert app._route == "/settings"


def test_settings_change_reaches_the_profile_file() -> None:
    """Правка в виджете доходит до хранилища и до файла профиля."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    app._open_settings("global")
    session = app.manager.get_active()
    assert session is not None and session.view is not None

    row = next(r for r in session.view.panel.rows if r.spec.key == "log_level")
    assert row.commit("DEBUG") is True
    assert app.settings.get("global", "log_level") == "DEBUG"


def test_settings_change_is_applied_to_live_terminal() -> None:
    """Изменение внешнего вида применяется к уже открытой вкладке терминала."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    item = app.manager.open("terminal", title="Terminal (pyte)")
    app._refresh_workspace()
    before = item._view._font_size

    app.settings.set("terminal-pyte", "font_size", before + 4, save=False)
    assert app.applier.apply_key("terminal-pyte", "font_size") is True
    assert item._view._font_size == before + 4


def test_settings_survive_a_restart() -> None:
    """Настройка, сохранённая вкладкой, видна после перезапуска приложения."""
    first = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    first.start()
    first.settings.set("terminal-pyte", "font_size", 21, save=True)

    second = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    second.start()
    assert second.settings.get("terminal-pyte", "font_size") == 21


def test_widget_change_subscription_reaches_the_applier() -> None:
    """Правка виджета доходит до applier'а через подписку хранилища."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    app._open_settings("global")
    session = app.manager.get_active()
    assert session is not None and session.view is not None

    row = next(r for r in session.view.panel.rows if r.spec.key == "log_level")
    assert row.commit("WARNING") is True
    import logging

    assert logging.getLogger().level == logging.WARNING


def test_closed_settings_tab_unsubscribes_from_the_store() -> None:
    """Закрытая вкладка отписывается: хранилище не держит её экран."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    app._open_settings("global")
    session = app.manager.get_active()
    assert session is not None
    before = app.settings.listener_count

    app.manager.close(session.session_id)
    assert app.settings.listener_count == before - 1


def test_startup_scan_picks_up_plugin_settings(tmp_path) -> None:
    """Плагин из профиля подхватывается автоматически при старте."""
    import json

    from core.settings.PluginSettingsScanner import SCHEMA_FILE

    plugin = tmp_path / "plugins" / "demo"
    plugin.mkdir(parents=True)
    (plugin / SCHEMA_FILE).write_text(
        json.dumps(
            {
                "slug": "demo-plugin",
                "title": "Demo",
                "settings": {
                    "greeting": {"type": "string", "label": "Greeting", "default": "hi"}
                },
            }
        ),
        encoding="utf-8",
    )

    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    assert app.settings.schema.find("demo-plugin") is None

    asyncio.run(app._bootstrap())
    assert app.settings.schema.find("demo-plugin") is not None


def test_startup_scan_honours_disabled_plugins(tmp_path) -> None:
    """Отключённые плагины при старте не читаются из профиля."""
    import json

    from core.settings.PluginSettingsScanner import SCHEMA_FILE

    plugin = tmp_path / "plugins" / "demo"
    plugin.mkdir(parents=True)
    (plugin / SCHEMA_FILE).write_text(
        json.dumps(
            {
                "slug": "demo-plugin",
                "title": "Demo",
                "settings": {
                    "greeting": {"type": "string", "label": "Greeting", "default": "hi"}
                },
            }
        ),
        encoding="utf-8",
    )

    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    app.settings.set("plugins", "enable_plugins", False)

    app._scan_plugins()
    assert app.settings.schema.find("demo-plugin") is None


# --- Состояние главного окна и стартовый вид ---


def test_panels_start_collapsed() -> None:
    """При запуске обе выдвижные панели свёрнуты."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    assert app.layout.panel_visibility() == (False, False)


def test_no_tabs_are_open_at_startup(tmp_path) -> None:
    """Стартовые вкладки не открываются: рабочая область пуста.

    Штатный запуск идёт через `_bootstrap`, где сессия создаётся только если
    так сказано в настройках (`startup_session`), а её умолчание — `none`.
    """
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    asyncio.run(app._bootstrap())

    assert app.settings.get("global", "startup_session") == "none"
    assert app.manager.sessions == []
    assert _tabs(app) == []


def test_explicit_startup_session_setting_opens_a_tab() -> None:
    """Если пользователь выбрал сессию запуска, она открывается.

    Терминал не поднимаем: важен выбор `_bootstrap`, а не работа PTY.
    """
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()
    opened: list[str] = []
    app._open_terminal = lambda kind="terminal": opened.append(kind)  # type: ignore[method-assign]
    app.settings.set("global", "startup_session", "terminal-gpu", save=False)

    asyncio.run(app._bootstrap())
    assert opened == ["terminal-gpu"]


def test_panel_toggle_is_persisted_and_restored() -> None:
    """Раскрытие панели сохраняется при закрытии и возвращается при старте."""
    first = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    first.start()
    first._on_panel_toggle("right", True)
    first._save_window_state()

    second = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    second.start()
    assert second.layout.panel_visibility() == (False, True)


def test_collapsing_a_panel_is_also_persisted() -> None:
    """Свёрнутая пользователем панель не возвращается раскрытой."""
    first = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    first.start()
    first._on_panel_toggle("left", True)
    first._on_panel_toggle("left", False)
    first._save_window_state()

    second = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    second.start()
    assert second.layout.panel_visibility() == (False, False)


def test_nothing_is_written_before_the_window_closes(tmp_path) -> None:
    """До закрытия окна файл состояния не появляется.

    Требование по ресурсу SSD: состояние пишется один раз, при закрытии.
    Ни клик по шеврону, ни ресайз не должны трогать диск.
    """
    state_file = tmp_path / "window" / "state.json"
    page = _StubPage()
    app = TermoClubApp(page)  # type: ignore[arg-type]
    app.start()

    app._on_panel_toggle("left", True)
    app._on_panel_toggle("right", True)
    page.window.width, page.window.height = 1500, 950
    app._on_page_resize(SimpleNamespace(width=1500, height=950))

    assert not state_file.exists(), "до закрытия окна писать на диск нельзя"

    # Закрытие окна — вот теперь состояние фиксируется.
    app._save_window_state()
    assert state_file.exists()


def test_window_size_is_restored_from_the_profile() -> None:
    """Размер окна, записанный при выходе, применяется при следующем старте."""
    first_page = _StubPage()
    first = TermoClubApp(first_page)  # type: ignore[arg-type]
    first.start()
    first_page.window.width, first_page.window.height = 1024, 768
    first._save_window_state()

    page = _StubPage()
    second = TermoClubApp(page)  # type: ignore[arg-type]
    second.start()
    assert (page.window.width, page.window.height) == (1024.0, 768.0)


def test_resize_updates_memory_and_exit_writes_the_file(tmp_path) -> None:
    """Ресайз не пишет файл на каждый кадр, а выход — фиксирует размер.

    Перетаскивание рамки сыпет событиями; запись происходит один раз, при
    завершении работы.
    """
    import json

    state_file = tmp_path / "window" / "state.json"
    page = _StubPage()
    app = TermoClubApp(page)  # type: ignore[arg-type]
    app.start()

    page.window.width, page.window.height = 1300, 850
    app._on_page_resize(SimpleNamespace(width=1300, height=850))
    assert (app.window_state.state.width, app.window_state.state.height) == (1300, 850)
    assert not state_file.exists(), "ресайз не должен писать файл"

    app._save_window_state()
    saved = json.loads(state_file.read_text())
    assert (saved["width"], saved["height"]) == (1300, 850)


def test_exit_save_falls_back_to_the_last_resize_size(tmp_path) -> None:
    """Если `page.window` не отдаёт размер, берётся последний ресайз.

    В web-режиме запись в `page.window` может не менять реальное окно, и
    прочитанный размер окажется нулевым — тогда сохранять нечего, кроме
    уже увиденного в `on_resize`.
    """
    import json

    page = _StubPage()
    app = TermoClubApp(page)  # type: ignore[arg-type]
    app.start()

    app._on_page_resize(SimpleNamespace(width=1300, height=850))
    page.window.width, page.window.height = None, None
    app._save_window_state()

    saved = json.loads((tmp_path / "window" / "state.json").read_text())
    assert (saved["width"], saved["height"]) == (1300, 850)


def test_repeated_resize_with_same_size_keeps_state_untouched() -> None:
    """Событие с тем же размером не считается изменением."""
    app = TermoClubApp(_StubPage())  # type: ignore[arg-type]
    app.start()

    app._remember_window_size(1024, 768)
    app._remember_window_size(1024, 768)
    assert (app.window_state.state.width, app.window_state.state.height) == (1024, 768)


def test_unknown_initial_route_falls_back_to_home() -> None:
    """Незнакомая ссылка открывает главную, а не пустую рабочую область."""
    app = TermoClubApp(_StubPage("/no/such/page"))  # type: ignore[arg-type]
    app.start()
    assert app._route == "/"


def test_deep_link_opens_the_settings_tab() -> None:
    """Прямой переход на `/settings` открывает вкладку настроек.

    Раньше начальный маршрут жёстко считался главной, и ссылка на раздел
    приводила на главный экран.
    """
    app = TermoClubApp(_StubPage("/settings"))  # type: ignore[arg-type]
    app.start()

    assert app._route == "/settings"
    assert [item.kind for item in app.manager.sessions] == ["settings"]


def test_deep_link_to_logs_opens_the_logs_section() -> None:
    """Прямой переход на `/logs` открывает раздел логов."""
    app = TermoClubApp(_StubPage("/logs"))  # type: ignore[arg-type]
    app.start()
    assert app._route == "/logs"
