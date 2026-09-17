# termoclub/app/ui/settings/SettingsControls.py
"""Фабрика виджетов настроек: тип значения схемы -> контрол.

Тип значения в схеме полностью определяет виджет: строка — поле ввода,
число — поле с ползунком, дата — пикер даты, цвет — палитра, файл —
диалог выбора файла, список — выпадающий список или набор чекбоксов.
Добавить новый тип значения можно только вместе с новым контролом здесь,
поэтому «зоопарк» виджетов в разметке не появляется.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

import flet as ft

from app.ui.settings.BooleanSettingControl import BooleanSettingControl
from app.ui.settings.ChoiceSettingControl import (
    ChoiceSettingControl,
    MultiChoiceSettingControl,
)
from app.ui.settings.ColorSettingControl import ColorSettingControl
from app.ui.settings.DateTimeSettingControl import DateTimeSettingControl
from app.ui.settings.LinkSettingControl import LinkSettingControl
from app.ui.settings.NumberSettingControl import NumberSettingControl
from app.ui.settings.PathSettingControl import PathSettingControl
from app.ui.settings.SettingControl import SettingControl
from app.ui.settings.SettingsDeps import SettingsDeps
from app.ui.settings.TextSettingControl import TextSettingControl
from core.settings.Category import Category
from core.settings.SettingSpec import SettingSpec
from core.settings.SettingsStore import SettingsStore
from core.settings.ValueType import ValueType

logger = logging.getLogger(__name__)

#: Тип значения -> класс контрола.
_REGISTRY: dict[ValueType, type[SettingControl]] = {
    ValueType.STRING: TextSettingControl,
    ValueType.TEXT: TextSettingControl,
    ValueType.INTEGER: NumberSettingControl,
    ValueType.NUMBER: NumberSettingControl,
    ValueType.BOOLEAN: BooleanSettingControl,
    ValueType.DATE: DateTimeSettingControl,
    ValueType.TIME: DateTimeSettingControl,
    ValueType.DATETIME: DateTimeSettingControl,
    ValueType.COLOR: ColorSettingControl,
    ValueType.CHOICE: ChoiceSettingControl,
    ValueType.MULTI_CHOICE: MultiChoiceSettingControl,
    ValueType.FILE: PathSettingControl,
    ValueType.DIRECTORY: PathSettingControl,
    ValueType.IMAGE: PathSettingControl,
    ValueType.LINK: LinkSettingControl,
}


class SettingsControls:
    """Строит контрол для настройки по её типу из схемы."""

    def __init__(
        self,
        page: ft.Page,
        store: SettingsStore,
        deps: SettingsDeps,
        on_changed: Callable[[str, str], None] | None = None,
    ) -> None:
        self.page = page
        self.store = store
        self.deps = deps
        self.on_changed = on_changed

    def build(self, category: Category, spec: SettingSpec) -> SettingControl:
        """Контрол настройки (неизвестный тип — текстовое поле).

        Неизвестный тип не должен ломать всю категорию: вместо исключения
        показывается текстовый контрол, а причина уходит в лог.
        """
        builder = _REGISTRY.get(spec.type)
        if builder is None:
            logger.warning(
                "SettingsControls: unknown value type %r for %s.%s, falling back to text",
                spec.type,
                category.slug,
                spec.key,
            )
            return TextSettingControl(
                self.page, self.store, category, spec, self.on_changed
            )
        if builder is PathSettingControl:
            return builder(
                self.page, self.store, category, spec, self.on_changed,
                picker=self.deps.picker,
            )
        if builder is LinkSettingControl:
            return builder(
                self.page, self.store, category, spec, self.on_changed,
                picker=self.deps.picker, opener=self.deps.opener,
            )
        return builder(self.page, self.store, category, spec, self.on_changed)