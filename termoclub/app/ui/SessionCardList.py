# termoclub/app/ui/SessionCardList.py
"""Список карточек сессий в левой панели с перетаскиванием."""
from __future__ import annotations

import flet as ft

from app.ui.FontAwesome import FontAwesome
from app.ui.SessionCard import SessionCard
from app.ui.SessionCardData import SessionCardData


class SessionCardList:
    """Карточки вкладок workspace: пополняются по мере открытия сессий.

    Порядок — ручкой `grip-vertical` (ReorderableDragHandle), новое
    положение уходит в `on_reorder(old_index, new_index)`.
    """

    def __init__(
        self,
        on_select=None,
        on_close=None,
        on_reorder=None,
        on_new=None,
    ) -> None:
        self.on_select = on_select
        self.on_close = on_close
        self.on_reorder = on_reorder
        self.on_new = on_new
        self._count = ft.Text("0", size=12, color=ft.Colors.GREY)
        self._list = ft.ReorderableListView(
            expand=True,
            show_default_drag_handles=False,
            padding=8,
            on_reorder=self._handle_reorder,
        )

    def _handle_reorder(self, e) -> None:  # type: ignore[no-untyped-def]
        old, new = e.old_index, e.new_index
        if old is None or new is None:
            return
        if old < new:  # семантика Flutter: индекс после извлечения
            new -= 1
        if self.on_reorder is not None:
            self.on_reorder(old, new)

    def _row(self, data: SessionCardData) -> ft.Control:
        card = SessionCard(data, self.on_select, self.on_close).build()
        return ft.Container(
            key=data.session_id,
            content=ft.Row(
                [
                    ft.ReorderableDragHandle(
                        content=ft.Container(
                            content=FontAwesome.icon(
                                "grip-vertical", size=14, color=ft.Colors.GREY
                            ),
                            tooltip="Drag to reorder",
                            padding=ft.Padding(0, 8, 0, 8),
                        ),
                    ),
                    ft.Container(content=card, expand=True),
                ],
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )

    def sync(self, items: list[SessionCardData]) -> None:
        """Инкрементально сверяет список с сессиями (порядок сохраняет)."""
        self._list.controls = [self._row(data) for data in items]
        self._count.value = str(len(items))
        self._safe_update(self._list)
        self._safe_update(self._count)

    @staticmethod
    def _safe_update(control: ft.Control) -> None:
        try:
            control.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.

    def build(self) -> ft.Control:
        """Возвращает панель: заголовок + переупорядочиваемый список."""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Sessions", weight=ft.FontWeight.BOLD, size=14),
                        self._count,
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.ADD,
                            icon_size=16,
                            tooltip="New terminal",
                            on_click=lambda _: self.on_new()
                            if self.on_new
                            else None,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(),
                self._list,
            ],
            expand=True,
        )
