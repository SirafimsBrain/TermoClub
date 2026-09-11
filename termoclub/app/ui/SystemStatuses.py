# termoclub/app/ui/SystemStatuses.py
"""Панель системных статусов (правая часть head/top).

Сейчас — заглушка: две-три иконки Font Awesome. В будущем здесь будут
статусы процессов (цвет/иконка по состоянию). Метод `set_status`
уже сейчас позволяет обновить индикатор по имени.
"""
from __future__ import annotations

import flet as ft

from app.ui.FontAwesome import FontAwesome


class SystemStatuses:
    """Индикаторы системных статусов в верхней панели."""

    def __init__(self) -> None:
        self._indicators: dict[str, ft.Text] = {}
        self._control = ft.Row(
            [
                self._make_indicator("link", "wifi", ft.Colors.GREEN, "Link status"),
                self._make_indicator(
                    "notifications", "bell", ft.Colors.AMBER, "Notifications"
                ),
                self._make_indicator("health", "circle-check", ft.Colors.GREEN, "Health"),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _make_indicator(
        self, name: str, icon: str, color: str, tooltip: str
    ) -> ft.Container:
        glyph = FontAwesome.icon(icon, size=15, color=color)
        self._indicators[name] = glyph
        return ft.Container(content=glyph, tooltip=tooltip)

    def set_status(self, name: str, color: str) -> None:
        """Меняет цвет индикатора (заготовка под статусы процессов)."""
        glyph = self._indicators.get(name)
        if glyph is not None:
            glyph.color = color
            try:
                glyph.update()
            except RuntimeError:
                pass  # Control is not mounted on a page yet.

    def build(self) -> ft.Control:
        """Возвращает панель статусов."""
        return self._control
