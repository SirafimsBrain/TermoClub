# termoclub/app/ui/settings/ChoiceSettingControl.py
"""Виджеты выбора из списка: `choice` (один вариант) и `multi_choice`.

Одиночный выбор — выпадающий список; множественный — сегменты, если
вариантов мало (их видно все сразу), иначе компактный список с чекбоксами.
Варианты берутся из схемы, но схема может наполнять их динамически
(например, `plugins.disabled_plugins` — найденные плагины), поэтому список
перестраивается методом `refresh_choices`.
"""
from __future__ import annotations

import flet as ft

from app.ui.settings.SettingControl import SettingControl

#: Сколько вариантов ещё показываем сегментами, а не списком с чекбоксами.
SEGMENT_LIMIT = 4


class ChoiceSettingControl(SettingControl):
    """Один вариант из фиксированного списка."""

    def build_editor(self) -> ft.Control:
        """Выпадающий список вариантов схемы."""
        self._dropdown = ft.Dropdown(
            value=_key(self.value),
            options=self._options(),
            dense=True,
            text_size=13,
            width=self.EDITOR_WIDTH,
            enable_filter=len(self.spec.choices) > 8,
            disabled=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_select=self._on_select,
        )
        return self._dropdown

    def show_value(self, value: object) -> None:
        """Переносит значение хранилища в список."""
        if getattr(self, "_dropdown", None) is None:
            return
        self._dropdown.value = _key(value)
        self._safe_update(self._dropdown)

    def refresh_choices(self) -> None:
        """Перестраивает варианты (после пересканирования плагинов)."""
        if getattr(self, "_dropdown", None) is None:
            return
        self._dropdown.options = self._options()
        self._dropdown.value = _key(self.value)
        self._safe_update(self._dropdown)

    def _options(self) -> list[ft.DropdownOption]:
        """Варианты схемы в виде опций Flet."""
        return [
            ft.DropdownOption(key=choice.value, text=choice.label)
            for choice in self.spec.choices
        ]

    def _on_select(self, _event: ft.ControlEvent) -> None:
        """Пишет выбранный вариант."""
        self.commit(self._dropdown.value or "")


class MultiChoiceSettingControl(SettingControl):
    """Несколько вариантов из списка (сегменты или чекбоксы)."""

    def build_editor(self) -> ft.Control:
        """Сегменты для короткого списка, иначе — чекбоксы в столбик."""
        self._segments: ft.SegmentedButton | None = None
        self._checks: dict[str, ft.Checkbox] = {}
        selected = _selected(self.value)
        if len(self.spec.choices) <= SEGMENT_LIMIT:
            self._segments = ft.SegmentedButton(
                segments=[
                    ft.Segment(value=choice.value, label=ft.Text(choice.label, size=12))
                    for choice in self.spec.choices
                ],
                selected=set(selected),
                allow_multiple_selection=True,
                allow_empty_selection=True,
                show_selected_icon=False,
                on_change=self._on_segments,
                disabled=self.spec.readonly or self.category.readonly or self.store.readonly,
            )
            return self._segments
        return self._build_checks(selected)

    def show_value(self, value: object) -> None:
        """Переносит выбранные варианты в редактор."""
        selected = _selected(value)
        if self._segments is not None:
            self._segments.selected = set(selected)
            self._safe_update(self._segments)
            return
        for key, box in self._checks.items():
            box.value = key in selected
            self._safe_update(box)

    def refresh_choices(self) -> None:
        """Перестраивает список вариантов целиком (варианты приходят извне)."""
        selected = _selected(self.value)
        if self._segments is not None:
            self._segments.segments = [
                ft.Segment(value=choice.value, label=ft.Text(choice.label, size=12))
                for choice in self.spec.choices
            ]
            self._segments.selected = set(selected)
            self._safe_update(self._segments)
            return
        host = self._checks_host()
        if host is None:
            return
        host.controls = self._build_checks(selected).controls
        self._safe_update(host)

    def _build_checks(self, selected: set[str]) -> ft.Control:
        """Список чекбоксов для длинного перечня вариантов."""
        self._checks = {
            choice.value: ft.Checkbox(
                label=choice.label,
                value=choice.value in selected,
                label_style=ft.TextStyle(size=12),
                on_change=self._on_check,
                disabled=self.spec.readonly or self.category.readonly or self.store.readonly,
            )
            for choice in self.spec.choices
        }
        return ft.Column(
            list(self._checks.values()),
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            height=min(160, 28 * max(1, len(self._checks))),
            tight=True,
        )

    def _checks_host(self) -> ft.Column | None:
        """Колонка чекбоксов (или None, если выбран режим сегментов)."""
        editor = self.control_for_editor
        return editor if isinstance(editor, ft.Column) else None

    def _on_segments(self, _event: ft.ControlEvent) -> None:
        """Пишет выбранные сегменты (порядок — как в схеме)."""
        chosen = self._segments.selected or set()
        self.commit([c.value for c in self.spec.choices if c.value in chosen])

    def _on_check(self, _event: ft.ControlEvent) -> None:
        """Пишет выбранные чекбоксы (порядок — как в схеме)."""
        self.commit([c.value for c in self.spec.choices if self._checks[c.value].value])


def _key(value: object) -> str | None:
    """Значение -> ключ варианта (None, если значение не строка)."""
    return value if isinstance(value, str) else None


def _selected(value: object) -> set[str]:
    """Значение -> набор выбранных ключей."""
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    if isinstance(value, str) and value:
        return {value}
    return set()


__all__ = ["ChoiceSettingControl", "MultiChoiceSettingControl"]