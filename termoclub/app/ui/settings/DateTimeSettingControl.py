# termoclub/app/ui/settings/DateTimeSettingControl.py
"""Виджеты даты и времени: `date`, `time`, `datetime`.

Значения хранятся в том же виде, что и в схеме (`ValueCodec`): `date`,
`time` или `datetime`, а пустая строка означает «не задано». Правятся
они пикерами Flet — а это диалоги, которые открывает страница
(`page.show_dialog`), поэтому контрол собирает пикеры и переводит
выбранное значение в тип настройки.
"""
from __future__ import annotations

from datetime import date, datetime, time

import flet as ft

from app.ui.settings.SettingControl import SettingControl
from core.settings.ValueCodec import ValueCodec
from core.settings.ValueType import ValueType

#: Отображаемый формат (значение в хранилище хранится по формату кодека).
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"


class DateTimeSettingControl(SettingControl):
    """Дата, время или дата со временем (по пикеру на каждую часть)."""

    def build_editor(self) -> ft.Control:
        """Текст значения плюс кнопки открытия пикеров."""
        self._field = ft.TextField(
            value=self._text(self.value),
            hint_text=self._hint(),
            text_size=13,
            dense=True,
            width=170,
            read_only=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_submit=self._on_submit,
            on_blur=self._on_submit,
        )
        return ft.Row([self._field, *self._buttons()], spacing=4, tight=True)

    def show_value(self, value: object) -> None:
        """Переносит значение хранилища в поле."""
        if getattr(self, "_field", None) is None:
            return
        self._field.value = self._text(value)
        self._safe_update(self._field)

    def _buttons(self) -> list[ft.Control]:
        """Кнопки пикеров: дата, а для времени и `datetime` — ещё и время."""
        buttons = [
            ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                icon_size=18,
                tooltip="Pick a date",
                disabled=not self._editable,
                on_click=self._open_date,
            )
        ]
        if self.spec.type in (ValueType.TIME, ValueType.DATETIME):
            buttons.append(
                ft.IconButton(
                    icon=ft.Icons.SCHEDULE,
                    icon_size=18,
                    tooltip="Pick a time",
                    disabled=not self._editable,
                    on_click=self._open_time,
                )
            )
        return buttons

    @property
    def _editable(self) -> bool:
        """False для настроек только для чтения."""
        return not (self.spec.readonly or self.category.readonly or self.store.readonly)

    # --- Пикеры ---

    def _open_date(self, _event: ft.ControlEvent) -> None:
        """Открывает пикер даты с текущим значением настройки."""
        current = self._parts()
        picker = ft.DatePicker(
            value=current.date() if isinstance(current, datetime) else date.today(),
            on_change=self._on_date_change,
            help_text=self.spec.title,
        )
        self.page.show_dialog(picker)

    def _open_time(self, _event: ft.ControlEvent) -> None:
        """Открывает пикер времени с текущим значением настройки."""
        current = self._parts()
        initial = (
            current.time().replace(microsecond=0)
            if isinstance(current, datetime)
            else time(0, 0)
        )
        picker = ft.TimePicker(
            value=initial,
            on_change=self._on_time_change,
            help_text=self.spec.title,
        )
        self.page.show_dialog(picker)

    def _on_date_change(self, event: ft.ControlEvent) -> None:
        """Собирает значение после выбора даты (сохраняя время)."""
        picked = getattr(event.control, "value", None)
        if not isinstance(picked, (date, datetime)):
            return
        moment = datetime(picked.year, picked.month, picked.day)
        if self.spec.type is ValueType.DATETIME:
            current = self._parts()
            if isinstance(current, datetime):
                moment = moment.replace(hour=current.hour, minute=current.minute)
        self._apply(moment)

    def _on_time_change(self, event: ft.ControlEvent) -> None:
        """Собирает значение после выбора времени (сохраняя дату)."""
        picked = getattr(event.control, "value", None)
        if not isinstance(picked, (time, datetime)):
            return
        current = self._parts()
        base = current if isinstance(current, datetime) else datetime.now()
        self._apply(
            base.replace(hour=picked.hour, minute=picked.minute, second=0, microsecond=0)
        )

    def _apply(self, moment: datetime) -> None:
        """Пишет собранное значение и показывает его в поле."""
        value = self._as_value(moment)
        self._field.value = self._text(value)
        self.commit(value)

    def _on_submit(self, _event: ft.ControlEvent) -> None:
        """Пишет значение, введённое текстом (пустое — «не задано»)."""
        text = (self._field.value or "").strip()
        if not text:
            self.commit("")
            return
        parsed = self._parse_text(text)
        if parsed is None:
            self.show_error(f"{self.spec.title}: cannot parse {text!r} ({self._hint()})")
            return
        self.commit(parsed)

    # --- Разбор и форматирование ---

    def _parts(self) -> date | time | datetime | None:
        """Текущее значение настройки (None, если оно пустое)."""
        value = self.value
        return value if isinstance(value, (date, time, datetime)) else None

    def _as_value(self, moment: datetime) -> object:
        """`datetime` -> значение типа настройки."""
        if self.spec.type is ValueType.DATE:
            return moment.date()
        if self.spec.type is ValueType.TIME:
            return moment.time().replace(second=0, microsecond=0)
        return moment

    def _parse_text(self, text: str) -> object | None:
        """Текст поля -> значение типа настройки (None — не разобрать)."""
        if self.spec.type is ValueType.DATE:
            return ValueCodec.parse_date(text)
        if self.spec.type is ValueType.TIME:
            parsed = ValueCodec.parse_time(text)
            if parsed is None:
                parsed = ValueCodec.parse_time(f"{text}:00")
            return parsed
        parsed = ValueCodec.parse_datetime(text)
        if parsed is not None:
            return parsed
        day = ValueCodec.parse_date(text)
        return day if day is not None else None

    def _text(self, value: object) -> str:
        """Значение настройки -> текст поля."""
        if isinstance(value, datetime):
            return value.strftime(DATETIME_FORMAT)
        if isinstance(value, date):
            return value.strftime(DATE_FORMAT)
        if isinstance(value, time):
            return value.strftime(TIME_FORMAT)
        return ""

    def _hint(self) -> str:
        """Подсказка формата ввода."""
        return {
            ValueType.DATE: "YYYY-MM-DD",
            ValueType.TIME: "HH:MM",
            ValueType.DATETIME: "YYYY-MM-DD HH:MM",
        }.get(self.spec.type, "")