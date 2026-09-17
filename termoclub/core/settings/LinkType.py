# termoclub/core/settings/LinkType.py
"""Тип ссылки для настроек с типом `ValueType.LINK`.

Ссылка хранится строкой (адрес или путь), но её *смысл* задаётся схемой:
пользователю показывается нужный редактор (диалог файла, диалог каталога,
открытие в браузере), а приложению — способ проверки и применения.
"""
from __future__ import annotations

from enum import Enum


class LinkType(str, Enum):
    """Что означает строка ссылки."""

    URL = "url"  # внешний адрес (http/https)
    FILE = "file"  # путь к файлу или к программе
    DIRECTORY = "directory"  # путь к каталогу
    EMAIL = "email"  # адрес электронной почты
    ROUTE = "route"  # внутренний маршрут приложения (/logs)

    @classmethod
    def coerce(cls, raw: str) -> "LinkType":
        """Строит тип ссылки из строки схемы."""
        try:
            return cls(raw)
        except ValueError:
            raise ValueError(f"Unknown link type: {raw!r}") from None