# termoclub/app/ui/settings/ColorSettingControl.py
"""Виджет настроек цвета: поле значения, образец и палитра быстрого выбора.

Значение хранится строкой `#RRGGBB`. Отдельного диалога выбора цвета во
Flet нет, поэтому цвет вводится текстом, а палитра частых цветов и
образец рядом с полем нужны, чтобы не набирать код вручную.
"""
from __future__ import annotations

import flet as ft

from app.ui.settings.SettingControl import MUTED, SettingControl

#: Частые цвета терминалов и темы (быстрый выбор).
PALETTE: list[tuple[str, str]] = [
    ("#000000", "Black"),
    ("#1E1E1E", "Surface"),
    ("#FFFFFF", "White"),
    ("#E53935", "Red"),
    ("#43A047", "Green"),
    ("#FDD835", "Yellow"),
    ("#1E88E5", "Blue"),
    ("#8E24AA", "Magenta"),
    ("#00ACC1", "Cyan"),
]


class ColorSettingControl(SettingControl):
    """Цвет `#RRGGBB` с образцом и палитрой быстрого выбора."""

    def build_editor(self) -> ft.Control:
        """Образец цвета, поле значения и меню палитры."""
        value = _normalize(self.value)
        self._preview = ft.Container(
            width=24,
            height=24,
            border_radius=4,
            bgcolor=value or None,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        )
        self._field = ft.TextField(
            value=value,
            hint_text="#RRGGBB",
            text_size=13,
            dense=True,
            width=140,
            read_only=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_submit=self._on_submit,
            on_blur=self._on_submit,
        )
        self._palette_button = ft.PopupMenuButton(
            icon=ft.Icons.PALETTE,
            icon_size=18,
            tooltip="Palette",
            items=[self._palette_item(code, name) for code, name in PALETTE],
            disabled=self.spec.readonly or self.category.readonly or self.store.readonly,
        )
        return ft.Row(
            [self._preview, self._field, self._palette_button],
            spacing=6,
            tight=True,
        )

    def show_value(self, value: object) -> None:
        """Переносит значение хранилища в поле и образец."""
        text = _normalize(value)
        if getattr(self, "_field", None) is not None:
            self._field.value = text
            self._safe_update(self._field)
        if getattr(self, "_preview", None) is not None:
            self._preview.bgcolor = text or None
            self._safe_update(self._preview)

    def _palette_item(self, code: str, name: str) -> ft.PopupMenuItem:
        """Пункт палитры: образец + подпись."""
        return ft.PopupMenuItem(
            content=ft.Row(
                [
                    ft.Container(width=16, height=16, border_radius=3, bgcolor=code),
                    ft.Text(name, size=12),
                    ft.Container(expand=True),
                    ft.Text(code, size=11, color=MUTED),
                ],
                spacing=8,
            ),
            on_click=lambda _e, value=code: self._pick(value),
        )

    def _pick(self, code: str) -> None:
        """Пишет цвет, выбранный из палитры."""
        self._field.value = code
        self.show_value(code)
        self.commit(code)

    def _on_submit(self, _event: ft.ControlEvent) -> None:
        """Пишет введённый цвет."""
        self.commit(_normalize(self._field.value))


def _normalize(value: object) -> str:
    """Значение -> строка цвета `#RRGGBB` (или как есть, если это не цвет)."""
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        return ""
    return text if text.startswith("#") else f"#{text}"