# termoclub/core/sessions/terminal/TerminalSession_test.py
"""Тесты pyte-сессии терминала (без страницы)."""
from __future__ import annotations

import flet as ft

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.TerminalSession import TerminalSession, key_to_bytes


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


def test_key_mapping() -> None:
    """Клавиши маппятся в байты PTY."""
    assert key_to_bytes("a") == b"a"
    assert key_to_bytes("Enter") == b"\r"
    assert key_to_bytes("Backspace") == b"\x7f"
    assert key_to_bytes("Tab") == b"\t"
    assert key_to_bytes("Escape") == b"\x1b"
    assert key_to_bytes("Arrow Up") == b"\x1b[A"
    assert key_to_bytes("Delete") == b"\x1b[3~"
    assert key_to_bytes("c", ctrl=True) == b"\x03"
    assert key_to_bytes("C", ctrl=True) == b"\x03"
    assert key_to_bytes("x", alt=True) == b"\x1bx"
    assert key_to_bytes("Shift") is None
    assert key_to_bytes("Control") is None
    assert key_to_bytes("F5") == b"\x1b[15~"


def test_initial_state_and_content() -> None:
    """Новая сессия: статус CREATED, контент строится один раз."""
    session = TerminalSession(title="ops")
    assert session.kind == "terminal"
    assert session.icon == "terminal"
    assert session.status == SessionStatus.CREATED
    first = session.get_content()
    assert isinstance(first, ft.Control)
    assert session.get_content() is first


def test_pty_feed_renders_to_display() -> None:
    """Вывод PTY проходит pyte и виден в display_text."""
    session = TerminalSession()
    session.get_content()
    session._on_pty_data(b"hello-pyte\r\n")
    assert "hello-pyte" in session.display_text


def test_handle_key_writes_to_bridge() -> None:
    """Клавиша уходит в мост (до start() — тихо игнорируется)."""
    session = TerminalSession()
    assert session.handle_key(_key("a")) is True
    assert session.handle_key(_key("Shift")) is False


def test_start_registers_pump_task() -> None:
    """start() переводит в RUNNING и планирует pump через page."""
    session = TerminalSession()
    page = _FakePage()
    session.start(page)  # type: ignore[arg-type]
    assert session.status == SessionStatus.RUNNING
    assert len(page.tasks) == 1


def test_focus_blur_transitions() -> None:
    """Фокус переключает RUNNING <-> FOCUSED."""
    session = TerminalSession()
    session._status = SessionStatus.RUNNING
    session.on_focus()
    assert session.status == SessionStatus.FOCUSED
    session.on_blur()
    assert session.status == SessionStatus.RUNNING


def test_cleanup_without_start_is_safe() -> None:
    """cleanup() до start() безопасен и закрывает сессию."""
    session = TerminalSession()
    session.cleanup()
    assert session.status == SessionStatus.CLOSED
