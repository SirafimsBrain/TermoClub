# termoclub/app/ui/settings/BooleanSettingControl.py
"""Виджет настроек типа «да/нет»: переключатель Switch."""

from __future__ import annotations

import flet as ft

from app.ui.settings.SettingControl import SettingControl


class BooleanSettingControl(SettingControl):
    """Булево значение — `Switch` в колонке редактора."""

    def build_editor(self) -> ft.Control:
        """Переключатель (пишет значение сразу при изменении)."""
        self._switch = ft.Switch(
            value=bool(self.value),
            on_change=self._on_change,
            disabled=self.spec.readonly or self.category.readonly or self.store.readonly,
        )
        return self._switch

    def show_value(self, value: object) -> None:
        """Переносит значение хранилища в переключатель."""
        if getattr(self, "_switch", None) is None:
            return
        self._switch.value = bool(value)
        self._safe_update(self._switch)

    def _on_change(self, _event: ft.ControlEvent) -> None:
        """Пишет выбранное состояние."""
        self.commit(bool(self._switch.value))