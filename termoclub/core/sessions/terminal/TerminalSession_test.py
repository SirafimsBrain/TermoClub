# termoclub/core/sessions/terminal/TerminalSession_test.py
"""Тесты pyte-сессии терминала (без страницы): каналы ввода и жизненный цикл."""
from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.TerminalSession import TerminalSession


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


def _collected(session: TerminalSession) -> list[bytes]:
    """Подменяет запись в PTY сборщиком байт."""
    written: list[bytes] = []
    session._bridge.write = written.append  # type: ignore[method-assign]
    return written


def test_initial_state_and_content() -> None:
    """Новая сессия: статус CREATED, контент строится один раз."""
    session = TerminalSession(title="ops")
    assert session.kind == "terminal"
    assert session.icon == "terminal"
    assert session.status == SessionStatus.CREATED
    first = session.get_content()
    assert isinstance(first, ft.Control)
    assert session.get_content() is first


def test_start_registers_pump_task() -> None:
    """start() переводит в RUNNING и планирует pump через page."""
    session = TerminalSession()
    page = _FakePage()
    session.start(page)  # type: ignore[arg-type]
    assert session.status == SessionStatus.RUNNING
    assert len(page.tasks) == 1


def test_pty_output_renders_to_display() -> None:
    """Вывод PTY проходит pyte и виден в display_text."""
    session = TerminalSession()
    session.get_content()
    session._on_pty_data(b"hello-pyte\r\n")
    assert "hello-pyte" in session.display_text


def test_hidden_field_owns_printable_input() -> None:
    """Печатаемые символы уходят через скрытое поле, а не через диспетчер."""
    session = TerminalSession()
    session.get_content()
    written = _collected(session)
    session._view._on_field_change(
        SimpleNamespace(data="Привет", control=SimpleNamespace(value=""))
    )
    assert written == ["Привет".encode("utf-8")]
    assert session.handle_key(_key("a")) is False
    assert written == ["Привет".encode("utf-8")]


def test_service_keys_go_through_dispatcher() -> None:
    """Служебные клавиши обрабатывает диспетчер клавиш."""
    session = TerminalSession()
    session.get_content()
    written = _collected(session)
    assert session.handle_key(_key("Backspace")) is True
    assert session.handle_key(_key("Arrow Up")) is True
    assert session.handle_key(_key("c", ctrl=True)) is True
    assert written == [b"\x7f", b"\x1b[A", b"\x03"]
    assert session.handle_key(_key("Shift")) is False


def test_input_without_hidden_field_falls_back_to_dispatcher() -> None:
    """До монтирования поля ввода печатаемые клавиши берёт диспетчер."""
    session = TerminalSession()
    written = _collected(session)
    assert session.handle_key(_key("a")) is True
    assert written == [b"a"]


def test_shift_control_paste_uses_clipboard() -> None:
    """Ctrl+Shift+V не уходит в PTY, а запрашивает вставку из буфера."""
    session = TerminalSession()
    session.get_content()
    written = _collected(session)
    pasted: list[int] = []
    session.paste = lambda: pasted.append(1)  # type: ignore[method-assign]
    assert session.handle_key(_key("V", ctrl=True, shift=True)) is True
    assert pasted == [1]
    assert written == []


def test_paste_shortcuts_without_hidden_field() -> None:
    """До монтирования поля ввода вставку забирает диспетчер клавиш."""
    session = TerminalSession()
    pasted: list[int] = []
    session.paste = lambda: pasted.append(1)  # type: ignore[method-assign]
    assert session.handle_key(_key("V", ctrl=True)) is True
    assert session.handle_key(_key("Insert", shift=True)) is True
    assert pasted == [1, 1]


def test_resize_updates_screen_and_pty() -> None:
    """resize() меняет экран и окно PTY, повторный размер игнорируется."""
    session = TerminalSession()
    session.get_content()
    resized: list[tuple[int, int]] = []
    session._bridge.resize = lambda c, l: resized.append((c, l))  # type: ignore[method-assign]
    session.resize(100, 30)
    assert (session._screen.columns, session._screen.lines) == (100, 30)
    assert resized == [(100, 30)]
    session.resize(100, 30)
    assert resized == [(100, 30)]


def test_focus_blur_transitions() -> None:
    """Фокус переключает RUNNING <-> FOCUSED (контрол не примонтирован)."""
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
