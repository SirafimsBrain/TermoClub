# termoclub/core/settings/ValueCodec.py
"""Валидация и приведение значений настроек к типу схемы.

Единственное место, где значение проверяется и нормализуется. GUI отдаёт
то, что ввёл пользователь (строку из поля, bool переключателя, список
тегов), а хранилище получает уже приведённое значение либо
`SettingsValidationError` с человекочитаемым текстом.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

from core.settings.SettingSpec import SettingSpec
from core.settings.SettingsValidationError import SettingsValidationError
from core.settings.ValueType import ValueType

#: Строковые форматы даты/времени, которыми оперирует схема.
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

#: Цвет: шесть hex-цифр, необязательный ведущий `#`.
_COLOR_RE = re.compile(r"^#?(?P<hex>[0-9a-fA-F]{6})$")

#: Простейшая проверка адреса и почты (без притязаний на RFC).
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValueCodec:
    """Преобразование «сырое значение <-> значение схемы»."""

    @staticmethod
    def coerce(spec: SettingSpec, value: Any) -> Any:
        """Приводит значение к типу настройки или бросает ошибку."""
        kind = spec.type
        if kind is ValueType.BOOLEAN:
            return _boolean(spec, value)
        if kind is ValueType.INTEGER:
            return _integer(spec, value)
        if kind is ValueType.NUMBER:
            return _number(spec, value)
        if kind is ValueType.CHOICE:
            return _choice(spec, value)
        if kind is ValueType.MULTI_CHOICE:
            return _multi_choice(spec, value)
        return _text_value(spec, value)

    @staticmethod
    def normalize(spec: SettingSpec, value: Any) -> Any:
        """Как `coerce`, но непригодное значение заменяет умолчанием.

        Используется при чтении файлов: битое или устаревшее значение из
        JSON не должно ломать окно настроек — оно молча откатывается к
        умолчанию из схемы (и логируется вызывающей стороной).
        """
        try:
            return ValueCodec.coerce(spec, value)
        except SettingsValidationError:
            return spec.default

    @staticmethod
    def to_json(spec: SettingSpec, value: Any) -> Any:
        """Значение схемы -> то, что попадёт в JSON."""
        if spec.type is ValueType.DATE and isinstance(value, date):
            return value.strftime(DATE_FORMAT)
        if spec.type is ValueType.DATETIME and isinstance(value, datetime):
            return value.strftime(DATETIME_FORMAT)
        if spec.type is ValueType.TIME and isinstance(value, time):
            return value.strftime(TIME_FORMAT)
        if spec.type is ValueType.MULTI_CHOICE:
            return list(value)
        return value

    @staticmethod
    def from_json(spec: SettingSpec, value: Any) -> Any:
        """Значение из JSON -> значение схемы (или умолчание).

        Битые даты, чужие варианты выбора и неверные типы не выбрасывают
        ошибку: хранилище обязано пережить правку файла руками.
        """
        if spec.type in (ValueType.DATE, ValueType.TIME, ValueType.DATETIME):
            try:
                return ValueCodec.coerce(spec, value)
            except SettingsValidationError:
                return spec.default
        return ValueCodec.normalize(spec, value)

    @staticmethod
    def parse_date(value: str) -> date | None:
        """Разбирает дату `YYYY-MM-DD` (для GUI-событий пикера)."""
        try:
            return datetime.strptime(value, DATE_FORMAT).date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_time(value: str) -> time | None:
        """Разбирает время `HH:MM:SS`."""
        try:
            return datetime.strptime(value, TIME_FORMAT).time()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_datetime(value: str) -> datetime | None:
        """Разбирает дату и время `YYYY-MM-DDTHH:MM:SS`."""
        try:
            return datetime.strptime(value, DATETIME_FORMAT)
        except (TypeError, ValueError):
            return None


def _fail(spec: SettingSpec, message: str) -> SettingsValidationError:
    """Ошибка валидации конкретной настройки."""
    return SettingsValidationError(spec.key, message)


def _boolean(spec: SettingSpec, value: Any) -> bool:
    """Приводит значение к bool (строки из GUI тоже принимаются)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off", ""):
            return False
    if isinstance(value, int):
        return bool(value)
    raise _fail(spec, f"expected a boolean, got {value!r}")


def _integer(spec: SettingSpec, value: Any) -> int:
    """Приводит значение к int и проверяет границы схемы."""
    if isinstance(value, bool):
        raise _fail(spec, "expected an integer, got a boolean")
    if isinstance(value, int):
        result = value
    elif isinstance(value, float) and value.is_integer():
        result = int(value)
    elif isinstance(value, str) and value.strip():
        try:
            result = int(float(value.strip()))
        except ValueError:
            raise _fail(spec, f"expected an integer, got {value!r}") from None
    else:
        raise _fail(spec, f"expected an integer, got {value!r}")
    return _bounds(spec, result)


def _number(spec: SettingSpec, value: Any) -> float:
    """Приводит значение к float и проверяет границы схемы."""
    if isinstance(value, bool):
        raise _fail(spec, "expected a number, got a boolean")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            result = float(value.strip().replace(",", "."))
        except ValueError:
            raise _fail(spec, f"expected a number, got {value!r}") from None
    else:
        raise _fail(spec, f"expected a number, got {value!r}")
    return _bounds(spec, result)


def _bounds(spec: SettingSpec, value: float) -> float:
    """Проверяет min/max из схемы."""
    if spec.minimum is not None and value < spec.minimum:
        raise _fail(spec, f"value {value} is below the minimum {spec.minimum}")
    if spec.maximum is not None and value > spec.maximum:
        raise _fail(spec, f"value {value} is above the maximum {spec.maximum}")
    return value


def _choice(spec: SettingSpec, value: Any) -> str:
    """Проверяет, что значение — один из вариантов схемы."""
    if not isinstance(value, str):
        raise _fail(spec, f"expected a choice value, got {value!r}")
    allowed = {choice.value for choice in spec.choices}
    if value not in allowed:
        raise _fail(spec, f"unknown choice {value!r} (allowed: {sorted(allowed)})")
    return value


def _multi_choice(spec: SettingSpec, value: Any) -> list[str]:
    """Проверяет список вариантов (порядок схемы, без дублей)."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise _fail(spec, f"expected a list of choices, got {value!r}")
    allowed = {choice.value for choice in spec.choices} or None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise _fail(spec, f"choice items must be strings, got {item!r}")
        if item not in result:
            result.append(item)
    if allowed is not None:
        unknown = [item for item in result if item not in allowed]
        if unknown:
            raise _fail(spec, f"unknown choices {unknown!r}")
    return result


def _text_value(spec: SettingSpec, value: Any) -> Any:
    """Строковые типы: текст, числа-строки, даты, цвета, ссылки, пути."""
    kind = spec.type
    if kind is ValueType.DATE:
        return _parse_date(spec, value)
    if kind is ValueType.TIME:
        return _parse_time(spec, value)
    if kind is ValueType.DATETIME:
        return _parse_datetime(spec, value)
    text = "" if value is None else str(value)
    if kind is ValueType.COLOR:
        return _color(spec, text)
    if kind is ValueType.LINK:
        return _link(spec, text)
    if spec.pattern and text and not re.fullmatch(spec.pattern, text):
        raise _fail(spec, f"{text!r} does not match {spec.pattern!r}")
    return text


def _parse_date(spec: SettingSpec, value: Any) -> date | str:
    """Строка/дата -> date; пустое значение означает «не задано»."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    parsed = ValueCodec.parse_date(text)
    if parsed is None:
        raise _fail(spec, f"expected a date (YYYY-MM-DD), got {value!r}")
    return parsed


def _parse_time(spec: SettingSpec, value: Any) -> time | str:
    """Строка/время -> time; пустое значение означает «не задано»."""
    if isinstance(value, time):
        return value
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    parsed = ValueCodec.parse_time(text)
    if parsed is None:
        raise _fail(spec, f"expected a time (HH:MM:SS), got {value!r}")
    return parsed


def _parse_datetime(spec: SettingSpec, value: Any) -> datetime | str:
    """Строка/datetime -> datetime; пустое значение означает «не задано»."""
    if isinstance(value, datetime):
        return value
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    parsed = ValueCodec.parse_datetime(text)
    if parsed is None:
        parsed_date = ValueCodec.parse_date(text)
        if parsed_date is not None:
            return datetime.combine(parsed_date, time())
    if parsed is None:
        raise _fail(spec, f"expected a date and time (YYYY-MM-DDTHH:MM:SS), got {value!r}")
    return parsed


def _color(spec: SettingSpec, text: str) -> str:
    """Цвет приводится к каноническому виду `#rrggbb`."""
    if not text:
        return ""
    match = _COLOR_RE.match(text.strip())
    if match is None:
        raise _fail(spec, f"expected a colour like #rrggbb, got {value_repr(text)}")
    return f"#{match.group('hex').lower()}"


def _link(spec: SettingSpec, text: str) -> str:
    """Ссылка проверяется по своему типу (`link_type`)."""
    if not text:
        return ""
    link_type = spec.link_type
    if link_type is None:
        return text
    value = text.strip()
    from core.settings.LinkType import LinkType  # локально: без цикла модулей

    if link_type is LinkType.URL and not _URL_RE.match(value):
        raise _fail(spec, f"expected an http(s) URL, got {value_repr(value)}")
    if link_type is LinkType.EMAIL and not _EMAIL_RE.match(value):
        raise _fail(spec, f"expected an e-mail address, got {value_repr(value)}")
    if link_type is LinkType.ROUTE and not value.startswith("/"):
        raise _fail(spec, f"expected an application route starting with '/', got {value_repr(value)}")
    return value


def value_repr(value: object) -> str:
    """Короткое представление значения для текста ошибки."""
    return repr(value if len(str(value)) <= 60 else f"{str(value)[:57]}...")