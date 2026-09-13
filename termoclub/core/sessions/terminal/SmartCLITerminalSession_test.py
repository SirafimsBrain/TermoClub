"""Тесты SmartCLITerminalSession (замена flet-terminal на smartcli-core)."""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import flet as ft
import pytest

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.SmartCLITerminalSession import SmartCLITerminalSession


def _key(key: str, **mods) -> ft.KeyboardEvent:
    return ft.KeyboardEvent(
        name="keyboard_event",
        key=key,
        shift=mods.get("shift", False),
        ctrl=mods.get("ctrl", False),
        alt=mods.get("alt", False),
        meta=mods.get("meta", False),
        control=None,
    )


class _FakePage:
    def __init__(self) -> None:
        self.tasks: list = []
        self.controls: list = []

    def run_task(self, handler, *args):
        self.tasks.append((handler, args))

        class _Future:
            cancelled = False

            def cancel(self) -> None:
                self.cancelled = True

        future = _Future()
        self.future = future
        return future

    def add(self, control):
        self.controls.append(control)


def _patch_smartcli():
    """Мокаем smartcli_core, чтобы тесты не требовали реальный PTY."""
    mock_smartcli_core = MagicMock()

    class MockScreenModel:
        def __init__(self, cols=80, rows=24):
            self.cols = cols
            self.rows = rows
            self.on_change = None
            self._text = ""

        def feed(self, data: bytes):
            pass

        def resize(self, cols: int, rows: int):
            self.cols = cols
            self.rows = rows

        def to_text(self) -> str:
            return self._text

    class MockPtySession:
        def __init__(self, cols=80, rows=24, backend=None):
            self.cols = cols
            self.rows = rows

        async def start(self, shell, args=None, cwd=None, env=None):
            pass

        def send_text(self, text: str):
            pass

        def send_signal(self, signal: str):
            pass

        def resize(self, cols: int, rows: int):
            self.cols = cols
            self.rows = rows

        def terminate(self):
            pass

    mock_smartcli_core.ScreenModel = MockScreenModel
    mock_smartcli_core.PtySession = MockPtySession
    return {'smartcli_core': mock_smartcli_core}


@pytest.fixture
def mock_smartcli():
    with patch.dict('sys.modules', _patch_smartcli()):
        yield


def test_initial_state_and_content() -> None:
    """Новая сессия: статус CREATED, контент строится один раз."""
    session = SmartCLITerminalSession(title="ops")
    assert session.kind == "terminal-gpu"
    assert session.icon == "terminal"
    assert session.status == SessionStatus.CREATED
    first = session.get_content()
    assert isinstance(first, ft.Control)
    assert session.get_content() is first


def test_start_transitions_to_running():
    """start() переводит сессию в статус RUNNING."""
    session = SmartCLITerminalSession()
    page = _FakePage()

    with patch.object(session, '_setup_smartcli') as mock_setup, \
         patch.object(session, '_setup_view'), \
         patch.object(session, '_start_pump_and_refresh'):
        session.start(page)

    assert session.status == SessionStatus.RUNNING
    mock_setup.assert_called_once()


def test_focus_blur_transitions() -> None:
    """Фокус переключает RUNNING <-> FOCUSED."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    session.on_focus()
    assert session.status == SessionStatus.FOCUSED
    session.on_blur()
    assert session.status == SessionStatus.RUNNING


def test_cleanup_without_start_is_safe() -> None:
    """cleanup() до start() безопасен и закрывает сессию."""
    session = SmartCLITerminalSession()
    session.cleanup()
    assert session.status == SessionStatus.CLOSED


def test_cleanup_cancels_pump_task():
    """cleanup() отменяет pump-задачу."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    mock_task = MagicMock()
    session._pump_future = mock_task

    session.cleanup()

    assert session.status == SessionStatus.CLOSED
    mock_task.cancel.assert_called_once()


def test_handle_key_ctrl_c_returns_true():
    """Ctrl+C не перехватывается под копирование."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    session._pty_session = MagicMock()

    assert session.handle_key(_key("c", ctrl=True)) is True
    assert session._pty_session.send_signal.called


def test_handle_key_service_keys():
    """Служебные клавиши работают через TerminalKeymap."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    session._pty_session = MagicMock()
    session._screen_model = MagicMock()

    # Создаем вид чтобы display_text работал
    session._view = MagicMock()
    session._view._text.spans = []

    result = session.handle_key(_key("Enter"))
    assert result is True


def test_handle_key_printable_chars_return_false():
    """Печатаемые символы обрабатываются скрытым полем ввода."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING

    # Печатаемая клавиша без модификаторов должна вернуть False
    result = session.handle_key(_key("a"))
    assert result is False


def test_resize_updates_screen_and_pty():
    """resize() меняет экран и окно PTY."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    session._screen = MagicMock()
    session._pty_session = MagicMock()
    
    session._on_resize(100, 30)
    session._screen.resize.assert_called_once_with(100, 30)
    session._pty_session.resize.assert_called_once_with(100, 30)


def test_on_input_bytes_writes_to_pty():
    """Ввод пользователя отправляется в PTY."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    session._pty_session = MagicMock()

    session._on_input_bytes(b"hello\n")
    session._pty_session.send_text.assert_called_once_with("hello\n")


def test_paste_requests_clipboard():
    """paste() запрашивает вставку из буфера обмена."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    session._page = _FakePage()
    session._page.get_clipboard_text = MagicMock(return_value="test text")
    session._pty_session = MagicMock()

    session.paste()

    session._page.get_clipboard_text.assert_called_once()
    session._pty_session.send_text.assert_called_once_with("test text")


def test_copy_uses_clipboard():
    """copy() помещает текст в буфер обмена."""
    session = SmartCLITerminalSession()
    session._page = _FakePage()
    session._page.set_clipboard_text = MagicMock()
    session._view = MagicMock()
    session._view._text.spans = []

    session.copy()
    session._page.set_clipboard_text.assert_called_once()


def test_start_creates_terminal_view():
    """start() создаёт TerminalView и контент."""
    session = SmartCLITerminalSession()
    page = _FakePage()

    with patch.object(session, '_setup_smartcli'), \
         patch('core.sessions.terminal.SmartCLITerminalSession.TerminalView') as MockView, \
         patch.object(session, '_start_pump_and_refresh'):
        mock_view = MockView.return_value
        mock_view.get_content.return_value = MagicMock(spec=ft.Control)
        session.start(page)

    assert session._view is not None
    # Проверяем, что TerminalView была создана с коллбэками
    MockView.assert_called_once()


def test_cleanup_with_running_session():
    """cleanup() для запущенной сессии завершает PTY."""
    session = SmartCLITerminalSession()
    session._status = SessionStatus.RUNNING
    mock_pty = MagicMock()
    session._pty_session = mock_pty
    session._content = MagicMock(spec=ft.Control)
    
    session.cleanup()
    
    assert session.status == SessionStatus.CLOSED
    mock_pty.terminate.assert_called_once()


def test_start_logs_error_on_failure():
    """Ошибка инициализации SmartCLI логируется и ставит статус ERROR."""
    session = SmartCLITerminalSession()
    page = MagicMock(spec=ft.Page)

    with patch.object(session, '_setup_smartcli', side_effect=Exception("init failed")):
        with pytest.raises(Exception):
            session.start(page)

    assert session.status == SessionStatus.ERROR


def test_display_text_returns_empty_when_no_view():
    """display_text пустой без инициализированного view."""
    session = SmartCLITerminalSession()
    assert session.display_text == ""


def test_get_content_returns_flet_control():
    """get_content() возвращает Flet контрол."""
    session = SmartCLITerminalSession()
    content = session.get_content()
    assert isinstance(content, ft.Control)