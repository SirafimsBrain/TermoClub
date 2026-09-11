# termoclub/app/workspace/WorkspaceWiring_test.py
"""Сквозной тест связки менеджер -> вкладки/сцена/карточки (без страницы)."""
from __future__ import annotations

import asyncio
import os

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


def test_key_dispatcher_roundtrip() -> None:
    """Клавиша: диспетчер -> PTY (cat) -> pump -> текст экрана."""
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        page = _StubPage()
        app = TermoClubApp(page)  # type: ignore[arg-type]
        app.start()
        item = app.manager.open("terminal", page, shell="/bin/cat", args=[])  # type: ignore[arg-type]
        await asyncio.wait_for(_wait_running(item), timeout=10)
        for ch in "hi":
            app._on_page_key(_key(ch))
        app._on_page_key(_key("Enter"))
        await asyncio.wait_for(_wait_text(item, "hi"), timeout=10)
        assert "hi" in item.display_text
        app.manager.close(item.session_id)

    asyncio.run(scenario())


async def _wait_running(item) -> None:  # type: ignore[no-untyped-def]
    while not item._bridge.running:
        await asyncio.sleep(0.02)


async def _wait_text(item, needle: str) -> None:  # type: ignore[no-untyped-def]
    while needle not in item.display_text:
        await asyncio.sleep(0.02)
