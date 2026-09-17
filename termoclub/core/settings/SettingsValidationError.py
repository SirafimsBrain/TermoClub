# termoclub/core/settings/SettingsValidationError.py
"""Ошибка валидации значения настройки."""
from __future__ import annotations

from core.settings.SettingsError import SettingsError


class SettingsValidationError(SettingsError):
    """Значение не соответствует типу/ограничениям из схемы."""

    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key}: {message}")
        self.key = key
        self.message = message