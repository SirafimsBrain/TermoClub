# termoclub/core/sessions/terminal/TerminalSession_test.py
"""Тесты pyte-сессии терминала (без страницы): каналы ввода и жизненный цикл."""
from __future__ import annotations

import asyncio
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
    """При фокусе в поле символы идут только через него — без дублирования."""
    session = TerminalSession()
    session.get_content()
    session._view._on_field_focus(None)  # autofocus поля до первого ввода
    written = _collected(session)
    session._view._on_field_change(
        SimpleNamespace(data="Привет", control=SimpleNamespace(value=""))
    )
    assert written == ["Привет".encode("utf-8")]
    assert session.handle_key(_key("a")) is False
    assert written == ["Привет".encode("utf-8")]


def test_service_keys_go_through_dispatcher() -> None:
    """Служебные клавиши работают и при фокусе в скрытом поле."""
    session = TerminalSession()
    session.get_content()
    session._view._on_field_focus(None)
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


def test_lost_focus_still_accepts_input_and_refocuses() -> None:
    """Потеря фокуса не должна «глушить» терминал: символы идут из диспетчера."""
    session = TerminalSession()
    session.get_content()
    written = _collected(session)
    focused: list[bool] = []
    session.focus_input = lambda: focused.append(True)  # type: ignore[method-assign]
    assert session.handle_key(_key("a")) is True
    assert written == [b"a"]
    assert focused == [True]


def test_content_renders_the_prompt_seen_before_mount() -> None:
    """Приглашение, пришедшее до монтирования, попадает на экран."""
    session = TerminalSession()
    session._on_pty_data(b"root@host:~# ")
    assert session._content is None
    control = session.get_content()
    assert isinstance(control, ft.Control)
    rendered = "".join(span.text or "" for span in session._view._text.spans)
    assert "root@host:~#" in rendered


def test_ctrl_c_stays_sigint() -> None:
    """Обычный Ctrl+C не перехватывается под копирование."""
    session = TerminalSession()
    session.get_content()
    written = _collected(session)
    assert session.handle_key(_key("c", ctrl=True)) is True
    assert written == [b"\x03"]


def test_copy_shortcuts_put_visible_screen_on_clipboard() -> None:
    """Ctrl+Shift+C и Ctrl+Insert копируют видимую область экрана."""
    session = TerminalSession()
    page = _FakePage()
    session._page = page  # type: ignore[assignment]
    session.get_content()
    session._on_pty_data(b"hello\r\nworld\r\n")
    copied: list[str] = []

    async def fake_copy(text: str) -> None:
        copied.append(text)

    session._copy_to_clipboard = fake_copy  # type: ignore[method-assign]
    assert session.handle_key(_key("C", ctrl=True, shift=True)) is True
    assert session.handle_key(_key("Insert", ctrl=True)) is True
    page.run_all()
    assert copied == ["hello\nworld", "hello\nworld"]


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


def test_plain_paste_shortcut_stays_with_the_focused_field() -> None:
    """Ctrl+V при фокусе в поле — вставка силами самого поля, без дубля."""
    session = TerminalSession()
    session.get_content()
    session._view._on_field_focus(None)
    written = _collected(session)
    pasted: list[int] = []
    session.paste = lambda: pasted.append(1)  # type: ignore[method-assign]
    assert session.handle_key(_key("V", ctrl=True)) is False
    assert pasted == []
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


def test_cleanup_cancels_the_pending_resize() -> None:
    """Хвостовая задача размера отменяется вместе с остальными."""
    session = TerminalSession()
    page = _FakePage()
    session._page = page  # type: ignore[assignment]
    session.get_content()
    session.resize(100, 30)
    assert session._resize_task is not None
    session.cleanup()
    assert session._resize_task is None
    assert session.status == SessionStatus.CLOSED


def test_resize_coalesces_the_layout_storm() -> None:
    """Анимация панелей схлопывается в два изменения размера, не в десятки.

    Первый размер применяется сразу (интерфейс отзывчив), остальные кадры
    не рассылаются, а последний применяется хвостовой задачей — иначе один
    toggle слал бы шеллу десятки SIGWINCH и столько же раз перерисовывал сетку.
    """
    session = TerminalSession()
    page = _FakePage()
    session._page = page  # type: ignore[assignment]
    session.get_content()
    resized: list[tuple[int, int]] = []
    session._bridge.resize = lambda c, l: resized.append((c, l))  # type: ignore[method-assign]

    session.resize(100, 30)
    assert resized == [(100, 30)]
    for columns in (110, 120, 130):
        session.resize(columns, 30)
    assert resized == [(100, 30)]
    page.run_all()
    assert resized == [(100, 30), (130, 30)]
    assert (session._screen.columns, session._screen.lines) == (130, 30)


def test_resize_before_mount_applies_immediately() -> None:
    """Без page хвостовой задачи нет: размер применяется синхронно."""
    session = TerminalSession()
    session.get_content()
    resized: list[tuple[int, int]] = []
    session._bridge.resize = lambda c, l: resized.append((c, l))  # type: ignore[method-assign]
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
