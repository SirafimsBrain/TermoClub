# termoclub/core/sessions/SessionFactory.py
"""Фабрика сессий рабочей области.

Создаёт сессии по типу (`terminal`, `editor`, `rdp`, ...) и позволяет
регистрировать новые. UI работает только с фабрикой и `WorkspaceItem`,
конкретные классы не импортирует.
"""
from __future__ import annotations

import logging

from core.sessions.WorkspaceItem import WorkspaceItem

logger = logging.getLogger(__name__)


def _terminal(**kwargs) -> WorkspaceItem:
    from core.sessions.terminal.TerminalSession import TerminalSession

    return TerminalSession(**kwargs)


def _terminal_gpu(**kwargs) -> WorkspaceItem:
    from core.sessions.terminal.SmartCLITerminalSession import SmartCLITerminalSession

    return SmartCLITerminalSession(**kwargs)


def _editor(**kwargs) -> WorkspaceItem:
    from core.sessions.editor.EditorSession import EditorSession

    return EditorSession(**kwargs)


def _rdp(**kwargs) -> WorkspaceItem:
    from core.sessions.rdp.RdpSession import RdpSession

    return RdpSession(**kwargs)


_REGISTRY: dict[str, callable] = {
    "terminal": _terminal,  # pyte + Flet: чистый Python, работает в stock-клиенте
    "terminal-gpu": _terminal_gpu,  # smartcli-toolkit: PTY и экран из smartcli_core
    "editor": _editor,
    "rdp": _rdp,
}


class SessionFactory:
    """Создаёт и регистрирует типы сессий рабочей области."""

    @staticmethod
    def create(kind: str, **kwargs) -> WorkspaceItem:
        """Создаёт сессию зарегистрированного типа."""
        try:
            builder = _REGISTRY[kind]
        except KeyError:
            raise ValueError(f"Unknown session kind: {kind!r}") from None
        item = builder(**kwargs)
        logger.info("SessionFactory: created %s session %s", kind, item.session_id)
        return item

    @staticmethod
    def register(kind: str, builder: callable) -> None:
        """Регистрирует новый тип сессии (например, pyte-рендер)."""
        _REGISTRY[kind] = builder
        logger.info("SessionFactory: registered session kind %r", kind)

    @staticmethod
    def kinds() -> list[str]:
        """Возвращает зарегистрированные типы сессий."""
        return sorted(_REGISTRY.keys())
