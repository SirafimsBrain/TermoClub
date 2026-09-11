# termoclub/app/ui/SessionCard.py
"""Карточка сессии в левой панели: мониторинг и управление (заготовка)."""
from __future__ import annotations

import flet as ft

from app.ui.FontAwesome import FontAwesome
from app.ui.SessionCardData import SessionCardData
from core.sessions.SessionStatus import SessionStatus

STATUS_COLORS = {
    SessionStatus.CREATED: ft.Colors.GREY,
    SessionStatus.RUNNING: ft.Colors.GREEN,
    SessionStatus.FOCUSED: ft.Colors.LIGHT_GREEN,
    SessionStatus.CLOSED: ft.Colors.GREY,
    SessionStatus.ERROR: ft.Colors.RED,
}


class SessionCard:
    """Карточка одной сессии: заголовок, статус, слоты под метрики/действия."""

    def __init__(
        self,
        data: SessionCardData,
        on_select=None,
        on_close=None,
    ) -> None:
        self.data = data
        self.on_select = on_select
        self.on_close = on_close

    def build(self) -> ft.Control:
        """Возвращает карточку (клик — фокус, крестик — закрыть)."""
        data = self.data

        def handle_select(_: ft.ControlEvent) -> None:
            if self.on_select is not None:
                self.on_select(data.session_id)

        def handle_close(_: ft.ControlEvent) -> None:
            if self.on_close is not None:
                self.on_close(data.session_id)

        dot = ft.Container(
            width=8,
            height=8,
            border_radius=4,
            bgcolor=STATUS_COLORS.get(data.status, ft.Colors.GREY),
        )
        return ft.Container(
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            padding=8,
            on_click=handle_select,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            FontAwesome.icon(data.icon, size=14),
                            ft.Column(
                                [
                                    ft.Text(data.title, size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"{data.source} · {data.kind}",
                                        size=10,
                                        color=ft.Colors.GREY,
                                    ),
                                ],
                                spacing=0,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=14,
                                on_click=handle_close,
                                style=ft.ButtonStyle(padding=0),
                            )
                            if data.can_close
                            else ft.Container(),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [dot, ft.Text(data.status.value, size=11)],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=4,
            ),
        )
