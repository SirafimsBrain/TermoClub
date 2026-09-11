# termoclub/core/sessions/SessionFactory_test.py
"""Тесты фабрики сессий."""
from __future__ import annotations

import pytest

from core.sessions.editor.EditorSession import EditorSession
from core.sessions.rdp.RdpSession import RdpSession
from core.sessions.SessionFactory import SessionFactory
from core.sessions.terminal.FletTerminalSession import FletTerminalSession
from core.sessions.terminal.TerminalSession import TerminalSession
from core.sessions.WorkspaceItem import WorkspaceItem


def test_create_terminal_editor_rdp() -> None:
    """Фабрика создаёт все зарегистрированные типы сессий."""
    assert isinstance(SessionFactory.create("terminal"), TerminalSession)
    assert isinstance(SessionFactory.create("terminal-gpu"), FletTerminalSession)
    assert isinstance(SessionFactory.create("editor"), EditorSession)
    assert isinstance(SessionFactory.create("rdp"), RdpSession)


def test_create_passes_kwargs() -> None:
    """Параметры пробрасываются в конструктор сессии."""
    item = SessionFactory.create("terminal", title="ops")
    assert item.title == "ops"


def test_create_unknown_kind_raises() -> None:
    """Неизвестный тип сессии — ValueError."""
    with pytest.raises(ValueError):
        SessionFactory.create("no-such-kind")


def test_register_custom_kind() -> None:
    """register() добавляет новый тип без изменений в UI."""

    class CustomSession(WorkspaceItem):
        KIND = "custom"

        def get_content(self):  # type: ignore[no-untyped-def]
            import flet as ft

            return ft.Text("custom")

        def cleanup(self) -> None:
            pass

    SessionFactory.register("custom", lambda **kwargs: CustomSession("C"))
    assert isinstance(SessionFactory.create("custom"), CustomSession)
    assert "custom" in SessionFactory.kinds()
