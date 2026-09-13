# termoclub/core/sessions/terminal/FletTerminalSession_test.py
"""Тесты сессии внутреннего терминала (без страницы)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import flet as ft
import pytest

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.FletTerminalSession import FletTerminalSession


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


class _FakePage:
    def __init__(self) -> None:
        self.tasks: list = []

    def run_task(self, handler, *args):  # type: ignore[no-untyped-def]
        self.tasks.append((handler, args))

        class _Future:
            cancelled = False

            def cancel(self) -> None:
                self.cancelled = True

        future = _Future()
        self.future = future
        return future


def test_initial_state_and_content() -> None:
    """Новая сессия: статус CREATED, контент строится один раз."""
    session = FletTerminalSession(title="ops")
    assert session.kind == "terminal-gpu"
    assert session.icon == "terminal"
    assert session.status == SessionStatus.CREATED
    first = session.get_content()
    assert isinstance(first, ft.Control)
    assert session.get_content() is first


def test_start_registers_pump_and_renderer_check() -> None:
    """start() переводит в RUNNING и планирует pump + проверку рендерера."""
    session = FletTerminalSession()
    page = _FakePage()
    session.start(page)  # type: ignore[arg-type]
    assert session.status == SessionStatus.RUNNING
    assert len(page.tasks) == 2


def test_focus_blur_transitions() -> None:
    """Фокус переключает RUNNING <-> FOCUSED (контрол не примонтирован)."""
    session = FletTerminalSession()
    session.get_content()
    session._status = SessionStatus.RUNNING
    session.on_focus()
    assert session.status == SessionStatus.FOCUSED
    session.on_blur()
    assert session.status == SessionStatus.RUNNING


def test_cleanup_without_start_is_safe() -> None:
    """cleanup() до start() безопасен и закрывает сессию."""
    session = FletTerminalSession()
    session.cleanup()
    assert session.status == SessionStatus.CLOSED


def test_paste_shortcuts_request_clipboard_paste() -> None:
    """Ctrl/⌘+V, Ctrl/⌘+Shift+V и Shift+Insert просят вставку из буфера."""
    session = FletTerminalSession()
    session.get_content()
    pasted: list[int] = []
    session.paste = lambda: pasted.append(1)  # type: ignore[method-assign]
    assert session.handle_key(_key("V", ctrl=True)) is True
    assert session.handle_key(_key("V", meta=True)) is True
    assert session.handle_key(_key("V", ctrl=True, shift=True)) is True
    assert session.handle_key(_key("Insert", shift=True)) is True
    assert pasted == [1, 1, 1, 1]


def test_other_keys_are_left_to_xterm() -> None:
    """Остальные клавиши обрабатывает Dart-сторона, в PTY дублей нет."""
    session = FletTerminalSession()
    session.get_content()
    written: list[bytes] = []
    session._bridge.write = written.append  # type: ignore[method-assign]
    for event in (_key("a"), _key("Enter"), _key("V"), _key("Backspace")):
        assert session.handle_key(event) is False
    assert written == []


def test_string_input_fallback_writes_to_bridge() -> None:
    """Без DataChannel ввод приходит строкой через on_data."""
    session = FletTerminalSession()
    session.get_content()
    written: list[bytes] = []
    session._bridge.write = written.append  # type: ignore[method-assign]
    session._on_terminal_data(SimpleNamespace(data="ok"))
    session._on_terminal_data(SimpleNamespace(data=""))
    assert written == [b"ok"]


def test_resize_event_sizes_the_pty() -> None:
    """Размер PTY берётся из on_resize xterm.dart, а не из пикселей."""
    session = FletTerminalSession()
    session.get_content()
    resized: list[tuple[int, int]] = []
    session._bridge.resize = lambda c, l: resized.append((c, l))  # type: ignore[method-assign]
    session._on_terminal_resize(SimpleNamespace(data='{"cols": 100, "rows": 30}'))
    session._on_terminal_resize(SimpleNamespace(data="not json"))
    session._on_terminal_resize(SimpleNamespace(data='{"cols": 0, "rows": 30}'))
    assert resized == [(100, 30)]


def test_copy_shortcuts_copy_the_selection() -> None:
    """Ctrl+Shift+C и Ctrl+Insert кладут выделение xterm в буфер."""
    session = FletTerminalSession()
    session.get_content()
    page = _FakePage()
    session._page = page  # type: ignore[assignment]
    assert session.handle_key(_key("C", ctrl=True, shift=True)) is True
    assert session.handle_key(_key("Insert", ctrl=True)) is True
    assert [handler for handler, _ in page.tasks] == [
        session._copy_selection,
        session._copy_selection,
    ]


def test_ctrl_c_is_left_to_the_shell() -> None:
    """Обычный Ctrl+C — сигнал для шелла, а не копирование."""
    session = FletTerminalSession()
    session.get_content()
    assert session.handle_key(_key("c", ctrl=True)) is False


def test_missing_dart_control_is_reported(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Без Dart-расширения сессия честно сообщает, что рендерить нечем."""
    monkeypatch.setattr(FletTerminalSession, "MOUNT_TIMEOUT", 0.01)
    events: list[str] = []
    session = FletTerminalSession(on_renderer_missing=events.append)

    class _LivePage:
        def run_task(self, handler, *args):  # type: ignore[no-untyped-def]
            return asyncio.ensure_future(handler(*args))

    async def idle() -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(session, "_run", idle)

    async def scenario() -> None:
        session.start(_LivePage())  # type: ignore[arg-type]
        await asyncio.sleep(0.1)

    asyncio.run(scenario())
    session.cleanup()
    assert len(events) == 1
    assert "flet build" in events[0]


def test_mounted_control_silences_the_check(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Если контрол смонтировался, ничего сообщать не надо."""
    monkeypatch.setattr(FletTerminalSession, "MOUNT_TIMEOUT", 0.01)
    events: list[str] = []
    session = FletTerminalSession(on_renderer_missing=events.append)

    class _LivePage:
        def run_task(self, handler, *args):  # type: ignore[no-untyped-def]
            return asyncio.ensure_future(handler(*args))

    async def idle() -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(session, "_run", idle)

    async def scenario() -> None:
        session.start(_LivePage())  # type: ignore[arg-type]
        session._on_terminal_mount(None)  # type: ignore[arg-type]
        await asyncio.sleep(0.1)

    asyncio.run(scenario())
    session.cleanup()
    assert events == []
