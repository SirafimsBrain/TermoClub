# termoclub/core/settings/SettingsError.py
"""Базовая ошибка слоя настроек."""
from __future__ import annotations


class SettingsError(Exception):
    """Ошибка работы с настройками (схема, файлы, хранилище)."""