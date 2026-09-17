# termoclub/app/ui/settings/NumberSettingControl.py
"""Виджет числовых настроек: поле ввода плюс ползунок, если есть границы.

`integer` и `number` отличаются только шагом округления. Когда схема задаёт
и минимум, и максимум, рядом с полем появляется `Slider` — так значение
меняется и «на глаз», и точно. Ползунок и поле всегда показывают одно и то
же значение: правка любого из них пишет его через хранилище.
"""
from __future__ import annotations

import flet as ft

from app.ui.settings.SettingControl import SettingControl
from core.settings.ValueType import ValueType


class NumberSettingControl(SettingControl):
    """Целое или дробное число с необязательными границами."""

    def build_editor(self) -> ft.Control:
        """Поле числа и (при заданных границах) ползунок под ним."""
        number = _as_float(self.value, 0.0)
        self._field = ft.TextField(
            value=_format(self.value, self.spec.type),
            text_size=13,
            dense=True,
            text_align=ft.TextAlign.RIGHT,
            suffix=ft.Text(self.spec.unit, size=11) if self.spec.unit else None,
            read_only=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_submit=self._on_submit,
            on_blur=self._on_submit,
            width=120,
        )
        self._slider = self._build_slider(number)
        if self._slider is None:
            return self._field
        return ft.Row([self._field, self._slider], spacing=8, tight=True)

    def show_value(self, value: object) -> None:
        """Переносит значение хранилища в поле и ползунок."""
        if getattr(self, "_field", None) is not None:
            self._field.value = _format(value, self.spec.type)
            self._safe_update(self._field)
        if getattr(self, "_slider", None) is not None:
            self._slider.value = _as_float(value, 0.0)
            self._safe_update(self._slider)

    def _build_slider(self, value: float) -> ft.Slider | None:
        """Ползунок для настроек с обеими границами."""
        if self.spec.minimum is None or self.spec.maximum is None:
            return None
        divisions = None
        if self.spec.step:
            span = self.spec.maximum - self.spec.minimum
            divisions = max(1, int(round(span / self.spec.step)))
        return ft.Slider(
            min=self.spec.minimum,
            max=self.spec.maximum,
            divisions=divisions,
            value=value,
            label="{value}" + (f" {self.spec.unit}" if self.spec.unit else ""),
            expand=True,
            disabled=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_change_end=self._on_slider,
        )

    def _on_slider(self, _event: ft.ControlEvent) -> None:
        """Отпускание ползунка пишет новое значение."""
        self.commit(_cast(self._slider.value, self.spec.type))

    def _on_submit(self, _event: ft.ControlEvent) -> None:
        """Enter или потеря фокуса в поле пишет новое значение."""
        self.commit(_cast(self._field.value, self.spec.type))


def _cast(value: object, kind: ValueType) -> object:
    """Приводит ввод к типу настройки (число или строка — если пусто)."""
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return text  # Пусть хранилище вернёт понятную ошибку валидации.
    return int(round(number)) if kind is ValueType.INTEGER else number


def _as_float(value: object, fallback: float) -> float:
    """Значение -> float для ползунка."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _format(value: object, kind: ValueType) -> str:
    """Значение -> текст поля (целые без дробной части)."""
    if isinstance(value, bool) or value is None:
        return ""
    if kind is ValueType.INTEGER:
        try:
            return str(int(float(value)))
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(value)
    return str(value)