# termoclub/core/sessions/editor/EditorSession.py
"""Сессия редактора (заглушка: плейсхолдер до реальной реализации)."""
from __future__ import annotations

import flet as ft

from core.sessions.WorkspaceItem import WorkspaceItem


class EditorSession(WorkspaceItem):
    """Вкладка редактора — пока заглушка для инфраструктуры вкладок."""

    KIND = "editor"

    def __init__(self, title: str = "Editor", session_id: str | None = None) -> None:
        super().__init__(title, session_id)

    @property
    def icon(self) -> str:
        return "file-lines"

    def get_content(self) -> ft.Control:
        if self._content is None:
            self._content = ft.Column(
                [
                    ft.Text(self.title, style=ft.TextThemeStyle.HEADLINE_SMALL),
                    ft.Text("Editor session is not implemented yet."),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
        return self._content

    def cleanup(self) -> None:
        from core.sessions.SessionStatus import SessionStatus

        self._status = SessionStatus.CLOSED
