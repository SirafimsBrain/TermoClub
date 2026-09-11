# termoclub/app/ui/WorkspaceStage.py
"""Хост контента вкладок: ft.Stack, переключение через visible."""
from __future__ import annotations

import flet as ft


class WorkspaceStage:
    """Контент workspace: контролы монтируются один раз и не пересоздаются.

    Переключение вкладок только меняет `visible`, поэтому состояние
    (например, буфер xterm) переживает смену фокуса.
    """

    def __init__(self) -> None:
        self._stack = ft.Stack(expand=True)
        self._mounted: dict[str, ft.Control] = {}

    def mount(self, session_id: str, control: ft.Control, visible: bool) -> None:
        """Монтирует контрол сессии (один раз)."""
        if session_id in self._mounted:
            return
        host = ft.Container(content=control, expand=True, visible=visible)
        self._mounted[session_id] = host
        self._stack.controls.append(host)
        self._safe_update()

    def show(self, session_id: str) -> None:
        """Показывает одну сессию, остальные прячет."""
        for sid, host in self._mounted.items():
            host.visible = sid == session_id
        self._safe_update()

    def remove(self, session_id: str) -> None:
        """Убирает контрол закрытой сессии."""
        host = self._mounted.pop(session_id, None)
        if host is not None and host in self._stack.controls:
            self._stack.controls.remove(host)
        self._safe_update()

    def prune(self, live_ids: set[str]) -> None:
        """Убирает контролы сессий, которых больше нет в менеджере."""
        for session_id in list(self._mounted.keys()):
            if session_id not in live_ids:
                self.remove(session_id)

    def _safe_update(self) -> None:
        try:
            self._stack.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.

    def build(self) -> ft.Control:
        """Возвращает хост контента."""
        return self._stack
