# termoclub/core/settings/SettingsScope.py
"""Область действия настройки: приложение или плагин.

Область определяет, в какой файл попадёт значение: настройки приложения —
в `~/.termoclub/settings/<категория>.json`, настройки плагина — в
`~/.termoclub/plugins/<плагин>/values.json`.
"""
from __future__ import annotations

from enum import Enum


class SettingsScope(str, Enum):
    """Где хранятся значения настроек."""

    APP = "app"  # основные настройки приложения
    PLUGIN = "plugin"  # настройки плагина (в его собственной папке)

    @classmethod
    def coerce(cls, raw: str) -> "SettingsScope":
        """Строит область из строки схемы."""
        try:
            return cls(raw)
        except ValueError:
            raise ValueError(f"Unknown settings scope: {raw!r}") from None