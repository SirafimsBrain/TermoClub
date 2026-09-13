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
    def __init__(self) -> None:
        self.fonts: dict | None = None
        self.added: list = []

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
    """Приглашение шелла отрисовано, а сетка влезает во вьюпорт по строкам.

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
        await asyncio.wait_for(_wait_prompt(item), timeout=10)

        rendered = _rendered(item)
        assert "#" in rendered or "$" in rendered
        # Строк ровно столько, сколько в сетке: лишние уехали бы в скролл.
        assert rendered.count("\n") == item._screen.lines - 1
        app.manager.close(item.session_id)

    asyncio.run(scenario())


async def _wait_prompt(item) -> None:  # type: ignore[no-untyped-def]
    """Ждёт, пока приглашение доедет именно до отрисовки, а не только до pyte."""
    while not any(mark in _rendered(item) for mark in "#$"):
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
