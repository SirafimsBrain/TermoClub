# termoclub/core/sessions/terminal/SmartCLITerminalSession_test.py
"""Тесты сессии терминала на smartcli-toolkit (`terminal-gpu`)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import flet as ft

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.SmartCLIPtyBridge import SmartCLIPtyBridge
from core.sessions.terminal.SmartCLIScreen import SmartCLIScreen
from core.sessions.terminal.SmartCLITerminalSession import SmartCLITerminalSession
from core.sessions.terminal.TerminalSession import TerminalSession


class _FakePage:
    """Минимальная страница: собирает задачи и всё, что на неё добавили."""

    def __init__(self) -> None:
        self.tasks: list = []
        self.added: list = []

    def add(self, *controls) -> None:  # type: ignore[no-untyped-def]
        self.added.extend(controls)

    def run_task(self, handler, *args):  # type: ignore[no-untyped-def]
        self.tasks.append((handler, args))

        class _Future:
            cancelled = False

            def cancel(self) -> None:
                self.cancelled = True

        return _Future()

    def run_all(self) -> None:
        """Выполняет поставленные задачи (корутины) синхронно."""
        for handler, args in self.tasks:
            asyncio.run(handler(*args))
        self.tasks.clear()


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


def _change(value: str) -> SimpleNamespace:
    return SimpleNamespace(data=value, control=SimpleNamespace(value=""))


def _collected(session: SmartCLITerminalSession) -> list[bytes]:
    """Подменяет запись в PTY сборщиком байт."""
    written: list[bytes] = []
    session._bridge.write = written.append  # type: ignore[method-assign]
    return written


def test_it_is_a_terminal_session_with_the_smartcli_engine() -> None:
    """Отличие от pyte-рендера — только движок: мост и экран из smartcli."""
    session = SmartCLITerminalSession(title="ops")
    assert isinstance(session, TerminalSession)
    assert session.kind == "terminal-gpu"
    assert session.icon == "terminal"
    assert isinstance(session._bridge, SmartCLIPtyBridge)
    assert isinstance(session._screen, SmartCLIScreen)


def test_initial_state_and_content() -> None:
    """Новая сессия: статус CREATED, контент строится один раз."""
    session = SmartCLITerminalSession(title="ops")
    assert session.status == SessionStatus.CREATED
    first = session.get_content()
    assert isinstance(first, ft.Control)
    assert session.get_content() is first
    # Пустой экран — это пробелы: pyte добивает строки до ширины экрана.
    assert session.display_text.strip() == ""
    assert session.copy_text() == ""


def test_control_is_never_added_to_the_page() -> None:
    """Контрол монтирует WorkspaceStage: `page.add()` давал вторую панель.

    Терминал, добавленный в корень страницы, оказывался отдельной панелью
    рядом с `ApplicationLayout`, а `get_content()` отдавал уже занятый
    контрол — вкладка оставалась пустой.
    """
    session = SmartCLITerminalSession()
    page = _FakePage()
    session.start(page)  # type: ignore[arg-type]
    assert isinstance(session.get_content(), ft.Control)
    assert page.added == []


def test_start_registers_the_pump_task() -> None:
    """start() переводит в RUNNING и планирует pump через page."""
    session = SmartCLITerminalSession()
    page = _FakePage()
    session.start(page)  # type: ignore[arg-type]
    assert session.status == SessionStatus.RUNNING
    assert len(page.tasks) == 1


def test_input_channels_match_the_pyte_renderer() -> None:
    """Ввод не дублируется: символы — из поля, служебные — из диспетчера."""
    session = SmartCLITerminalSession()
    session.get_content()
    session._view._on_field_focus(None)  # type: ignore[arg-type]
    written = _collected(session)
    session._view._on_field_change(_change("Привет"))
    assert written == ["Привет".encode("utf-8")]
    assert session.handle_key(_key("a")) is False
    assert session.handle_key(_key("Backspace")) is True
    assert session.handle_key(_key("c", ctrl=True)) is True
    assert written[1:] == [b"\x7f", b"\x03"]


def test_printable_input_without_focus_falls_back_to_dispatcher() -> None:
    """Потеря фокуса не глушит терминал: символ уходит из диспетчера."""
    session = SmartCLITerminalSession()
    session.get_content()
    written = _collected(session)
    focused: list[bool] = []
    session.focus_input = lambda: focused.append(True)  # type: ignore[method-assign]
    assert session.handle_key(_key("a")) is True
    assert written == [b"a"]
    assert focused == [True]


def test_copy_shortcuts_reach_the_clipboard() -> None:
    """Ctrl+Shift+C и Ctrl+Insert копируют видимую область экрана.

    Экран-адаптер читает ту же модель, поэтому общий с pyte-рендером код
    копирования работает без изменений.
    """
    session = SmartCLITerminalSession()
    page = _FakePage()
    session._page = page  # type: ignore[assignment]
    session.get_content()
    session._screen._model.feed(b"hello\r\nworld")
    collected: list[str] = []

    async def fake_copy(text: str) -> None:
        collected.append(text)

    session._copy_to_clipboard = fake_copy  # type: ignore[method-assign]
    assert session.handle_key(_key("C", ctrl=True, shift=True)) is True
    assert session.handle_key(_key("Insert", ctrl=True)) is True
    page.run_all()
    assert collected == ["hello\nworld", "hello\nworld"]


def test_plain_paste_stays_with_the_focused_field() -> None:
    """Ctrl+V при фокусе в поле — вставка силами самого поля, без дубля."""
    session = SmartCLITerminalSession()
    session.get_content()
    session._view._on_field_focus(None)  # type: ignore[arg-type]
    written = _collected(session)
    pasted: list[int] = []
    session.paste = lambda: pasted.append(1)  # type: ignore[method-assign]
    assert session.handle_key(_key("V", ctrl=True)) is False
    assert pasted == []
    assert written == []


def test_resize_coalesces_the_layout_storm() -> None:
    """Первый размер применяется сразу, последний — когда layout успокоится.

    Событие приходит на каждом кадре анимации выдвижных панелей: без
    склейки терминал слал бы шеллу десятки SIGWINCH и столько же раз
    перерисовывал сетку.
    """
    session = SmartCLITerminalSession()
    session.get_content()
    page = _FakePage()
    session._page = page  # type: ignore[assignment]
    resized: list[tuple[int, int]] = []
    session._bridge.resize = lambda c, l: resized.append((c, l))  # type: ignore[method-assign]

    session.resize(100, 30)
    assert resized == [(100, 30)]
    session.resize(110, 30)
    session.resize(120, 30)
    session.resize(130, 30)
    assert resized == [(100, 30)]  # кадры анимации не рассылаются
    page.run_all()  # хвостовое применение
    assert resized == [(100, 30), (130, 30)]
    assert (session._screen.columns, session._screen.lines) == (130, 30)


def test_resize_without_page_applies_immediately() -> None:
    """До монтирования (нет page) размер применяется синхронно, как раньше."""
    session = SmartCLITerminalSession()
    session.get_content()
    resized: list[tuple[int, int]] = []
    session._bridge.resize = lambda c, l: resized.append((c, l))  # type: ignore[method-assign]
    session.resize(100, 30)
    assert resized == [(100, 30)]


def test_focus_blur_transitions() -> None:
    """Фокус переключает RUNNING <-> FOCUSED."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    session.on_focus()
    assert session.status == SessionStatus.FOCUSED
    session.on_blur()
    assert session.status == SessionStatus.RUNNING


def test_cleanup_terminates_the_bridge() -> None:
    """cleanup() останавливает pump и гасит PTY, не трогая чужие задачи."""
    session = SmartCLITerminalSession()
    session.get_content()
    bridge = MagicMock()
    session._bridge = bridge  # type: ignore[assignment]
    session.cleanup()
    assert session.status == SessionStatus.CLOSED
    bridge.request_stop.assert_called_once()
    bridge.terminate.assert_called_once()


def test_cleanup_without_start_is_safe() -> None:
    """cleanup() до start() безопасен и закрывает сессию."""
    session = SmartCLITerminalSession()
    session.cleanup()
    assert session.status == SessionStatus.CLOSED
