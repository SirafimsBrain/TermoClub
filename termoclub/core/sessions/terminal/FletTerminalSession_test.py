# termoclub/core/sessions/terminal/FletTerminalSession_test.py
"""Тесты сессии внутреннего терминала (без страницы)."""
from __future__ import annotations

import flet as ft

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.FletTerminalSession import FletTerminalSession


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


def test_start_registers_pump_task() -> None:
    """start() переводит в RUNNING и планирует pump через page."""
    session = FletTerminalSession()
    page = _FakePage()
    session.start(page)  # type: ignore[arg-type]
    assert session.status == SessionStatus.RUNNING
    assert len(page.tasks) == 1


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
