# termoclub/app/ui/settings/TextSettingControl.py
"""Виджет настроек строкового типа: поле ввода (одно- и многострочное).

Типы `string` и `text` отличаются только числом строк: однострочное поле
сохраняется по `Enter` или потере фокуса, многострочное — по кнопке
«Сохранить», потому что `Enter` в нём переносит строку.
"""
from __future__ import annotations

import flet as ft

from app.ui.settings.SettingControl import SettingControl


class TextSettingControl(SettingControl):
    """Однострочный и многострочный текст."""

    def build_editor(self) -> ft.Control:
        """Поле ввода; многострочный вариант получает кнопку сохранения."""
        field = ft.TextField(
            value=str(self.value or ""),
            hint_text=self.spec.pattern or "",
            text_size=13,
            dense=True,
            multiline=self.spec.multiline,
            min_lines=2 if self.spec.multiline else 1,
            max_lines=4 if self.spec.multiline else 1,
            read_only=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_change=self._on_change if self.spec.multiline else None,
            on_submit=None if self.spec.multiline else self._on_submit,
            on_blur=None if self.spec.multiline else self._on_blur,
        )
        self._field = field
        if not self.spec.multiline:
            return field
        self._save_button = ft.TextButton("Save", on_click=self._on_save_click)
        return ft.Column([field, self._save_button], spacing=2, tight=True)

    def show_value(self, value: object) -> None:
        """Переносит значение хранилища в поле."""
        field = getattr(self, "_field", None)
        if field is None:
            return
        field.value = str(value or "")
        self._safe_update(field)

    # --- События ---

    def _on_change(self, _event: ft.ControlEvent) -> None:
        """Многострочное поле: правки копятся до нажатия «Сохранить»."""
        self.show_error("")

    def _on_save_click(self, _event: ft.ControlEvent) -> None:
        """Пишет многострочное значение в хранилище."""
        self._commit_text(self._field.value or "")

    def _on_submit(self, _event: ft.ControlEvent) -> None:
        """Enter в однострочном поле сохраняет значение."""
        self._commit_text(self._field.value or "")

    def _on_blur(self, _event: ft.ControlEvent) -> None:
        """Потеря фокуса сохраняет значение (как в большинстве настроек)."""
        self._commit_text(self._field.value or "")