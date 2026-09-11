# termoclub/app/ui/WorkspaceTabBar.py
"""Кастомная панель вкладок workspace: Row кнопок вместо ft.Tabs."""
from __future__ import annotations

import flet as ft

from app.ui.FontAwesome import FontAwesome
from app.ui.SessionCardData import SessionCardData


class WorkspaceTabBar:
    """Вкладки сессий: активная подсвечена, у каждой крестик, в конце "+".

    Только отображение: выбор/закрытие/создание уходят в колбэки.
    """

    def __init__(self, on_select=None, on_close=None, on_new=None) -> None:
        self.on_select = on_select
        self.on_close = on_close
        self.on_new = on_new
        self._row = ft.Row(
            [],
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _tab(self, data: SessionCardData) -> ft.Control:
        def handle_select(_: ft.ControlEvent) -> None:
            if self.on_select is not None:
                self.on_select(data.session_id)

        def handle_close(_: ft.ControlEvent) -> None:
            if self.on_close is not None:
                self.on_close(data.session_id)

        return ft.Container(
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
            if data.active
            else ft.Colors.TRANSPARENT,
            border_radius=6,
            padding=ft.Padding(8, 4, 4, 4),
            on_click=handle_select,
            content=ft.Row(
                [
                    FontAwesome.icon(data.icon, size=13),
                    ft.Text(data.title, size=13),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=13,
                        on_click=handle_close,
                        style=ft.ButtonStyle(padding=0),
                    )
                    if data.can_close
                    else ft.Container(),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def refresh(self, items: list[SessionCardData]) -> None:
        """Перерисовывает вкладки в порядке сессий менеджера."""
        tabs = [self._tab(data) for data in items]
        tabs.append(
            ft.IconButton(
                icon=ft.Icons.ADD,
                icon_size=16,
                tooltip="New terminal",
                on_click=lambda _: self.on_new() if self.on_new else None,
            )
        )
        self._row.controls = tabs
        try:
            self._row.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.

    def build(self) -> ft.Control:
        """Возвращает панель вкладок."""
        return self._row
