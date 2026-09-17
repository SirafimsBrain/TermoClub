# termoclub/core/settings/ValueType.py
"""Фиксированный список типов значений настроек.

Тип значения из схемы (`settings/*.json`) полностью определяет и способ
хранения в JSON, и виджет для правки: строка — поле ввода, число —
числовое поле, дата — пикер даты, цвет — пикер цвета, файл — диалог
выбора файла, список — выпадающий список или список с мультивыбором.
Зоопарк типов сознательно закрыт: расширять его можно только здесь.
"""
from __future__ import annotations

from enum import Enum


class ValueType(str, Enum):
    """Тип значения настройки."""

    STRING = "string"  # однострочный текст
    TEXT = "text"  # многострочный текст
    INTEGER = "integer"  # целое число
    NUMBER = "number"  # число с плавающей точкой
    BOOLEAN = "boolean"  # да/нет (переключатель)
    DATE = "date"  # дата (пикер даты)
    TIME = "time"  # время (пикер времени)
    DATETIME = "datetime"  # дата и время (два пикера)
    COLOR = "color"  # цвет `#RRGGBB`
    CHOICE = "choice"  # одно значение из списка (выпадающий список)
    MULTI_CHOICE = "multi_choice"  # несколько значений из списка
    FILE = "file"  # путь к файлу (диалог выбора файла)
    DIRECTORY = "directory"  # путь к директории (диалог выбора каталога)
    IMAGE = "image"  # путь к изображению (диалог + предпросмотр)
    LINK = "link"  # ссылка; тип ссылки задаётся отдельно (`LinkType`)

    @classmethod
    def coerce(cls, raw: str) -> "ValueType":
        """Строит тип из строки схемы; неизвестный тип — ошибка."""
        try:
            return cls(raw)
        except ValueError:
            raise ValueError(f"Unknown setting value type: {raw!r}") from None
