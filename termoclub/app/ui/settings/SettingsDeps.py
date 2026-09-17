# termoclub/app/ui/settings/SettingsDeps.py
"""Сервисы, нужные виджетам настроек помимо хранилища.

Часть контролов работает не только со значением, но и с системными
сервисами: диалогами выбора пути (`PathPicker`) и открытием ссылок
(`LinkOpener`). Они передаются одним объектом, чтобы фабрика контролов
собирала любой виджет одинаково.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ui.settings.LinkOpener import LinkOpener
from app.ui.settings.PathPicker import PathPicker


@dataclass(frozen=True)
class SettingsDeps:
    """Системные сервисы GUI-слоя настроек."""

    picker: PathPicker
    opener: LinkOpener