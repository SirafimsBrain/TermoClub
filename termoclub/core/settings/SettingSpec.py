# termoclub/core/settings/SettingSpec.py
"""Описание одной настройки: тип, значение по умолчанию, ограничения.

Схема — единственный источник правды: посредник (`SettingsStore`) по ней
валидирует значения, GUI-слой — выбирает виджет. Никаких «магических»
типов в разметке быть не должно.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.settings.Choice import Choice
from core.settings.LinkType import LinkType
from core.settings.ValueType import ValueType

#: Типы, значения которых хранятся в JSON строкой (в т.ч. числа и даты).
_STRINGY = frozenset(
    {
        ValueType.DATE,
        ValueType.TIME,
        ValueType.DATETIME,
        ValueType.COLOR,
        ValueType.FILE,
        ValueType.DIRECTORY,
        ValueType.IMAGE,
        ValueType.LINK,
    }
)


@dataclass
class SettingSpec:
    """Одна настройка: ключ, тип, умолчание, границы, подсказки."""

    key: str
    type: ValueType
    default: Any = None
    label: str = ""
    description: str = ""
    choices: list[Choice] = field(default_factory=list)
    link_type: LinkType | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    pattern: str | None = None
    unit: str = ""
    multiline: bool = False
    readonly: bool = False
    requires_restart: bool = False
    extensions: list[str] = field(default_factory=list)
    #: `applier` — как применить изменение к работающим терминалам
    #: (ключ живого применения; пусто — только сохранение).
    applier: str = ""

    @property
    def title(self) -> str:
        """Подпись настройки в GUI (по умолчанию — её ключ)."""
        return self.label or self.key

    @property
    def stores_text(self) -> bool:
        """True, если в JSON значение лежит строкой."""
        return self.type in _STRINGY

    @classmethod
    def from_dict(cls, key: str, payload: dict) -> "SettingSpec":
        """Строит описание из JSON-объекта схемы."""
        if not isinstance(payload, dict):
            raise ValueError(f"setting {key!r}: expected an object")
        raw_type = payload.get("type")
        if not isinstance(raw_type, str):
            raise ValueError(f"setting {key!r}: missing 'type'")
        spec = cls(key=key, type=ValueType.coerce(raw_type))
        spec.default = payload.get("default")
        spec.label = _text(payload, "label", key)
        spec.description = _text(payload, "description", "")
        spec.choices = _choices(key, payload.get("choices"))
        spec.link_type = _link_type(key, payload.get("link_type"), spec.type)
        spec.minimum = _number(key, payload.get("min"), spec.minimum)
        spec.maximum = _number(key, payload.get("max"), spec.maximum)
        spec.step = _number(key, payload.get("step"), spec.step)
        spec.pattern = _optional_text(payload.get("pattern"))
        spec.unit = _text(payload, "unit", "")
        spec.multiline = bool(payload.get("multiline", spec.type is ValueType.TEXT))
        spec.readonly = bool(payload.get("readonly", False))
        spec.requires_restart = bool(payload.get("requires_restart", False))
        spec.extensions = _string_list(key, payload.get("extensions"))
        spec.applier = _text(payload, "applier", "")
        _check_choices(key, spec)
        if spec.default is None:
            spec.default = _fallback_default(spec.type)
        return spec


def _text(payload: dict, name: str, fallback: str) -> str:
    """Строковое поле схемы с запасным значением."""
    value = payload.get(name)
    return value if isinstance(value, str) and value else fallback


def _fallback_default(kind: ValueType) -> object:
    """Умолчание по типу, когда схема его не задала."""
    if kind is ValueType.BOOLEAN:
        return False
    if kind is ValueType.INTEGER:
        return 0
    if kind is ValueType.NUMBER:
        return 0.0
    if kind is ValueType.MULTI_CHOICE:
        return []
    return ""


def _optional_text(value: object) -> str | None:
    """Необязательное строковое поле схемы."""
    return value if isinstance(value, str) and value else None


def _number(key: str, value: object, fallback: float | None) -> float | None:
    """Числовое поле схемы (int/float, но не bool)."""
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"setting {key!r}: expected a number, got {value!r}")
    return float(value)


def _string_list(key: str, value: object) -> list[str]:
    """Список строк из схемы (расширения файлов)."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(i, str) for i in value):
        raise ValueError(f"setting {key!r}: expected a list of strings")
    return list(value)


def _choices(key: str, value: object) -> list[Choice]:
    """Варианты выбора из схемы."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"setting {key!r}: 'choices' must be a list")
    try:
        return [Choice.from_dict(item) for item in value]
    except ValueError as exc:
        raise ValueError(f"setting {key!r}: {exc}") from None


def _link_type(key: str, value: object, kind: ValueType) -> LinkType | None:
    """Тип ссылки (обязателен для `link`, запрещён для остальных типов)."""
    if kind is not ValueType.LINK:
        if value is not None:
            raise ValueError(f"setting {key!r}: 'link_type' only applies to links")
        return None
    if not isinstance(value, str):
        raise ValueError(f"setting {key!r}: a link requires 'link_type'")
    try:
        return LinkType.coerce(value)
    except ValueError as exc:
        raise ValueError(f"setting {key!r}: {exc}") from None


def _check_choices(key: str, spec: SettingSpec) -> None:
    """Выбор из списка требует вариантов; мультивыбор может быть пустым.

    Пустой список вариантов у `multi_choice` — законный случай: варианты
    появляются позже (например, `disabled_plugins` наполняется найденными
    плагинами при сканировании). Пустой `choice` — ошибка схемы.
    """
    if spec.type is ValueType.CHOICE and not spec.choices:
        raise ValueError(f"setting {key!r}: choice requires 'choices'")
    if spec.type not in (ValueType.CHOICE, ValueType.MULTI_CHOICE) and spec.choices:
        raise ValueError(f"setting {key!r}: 'choices' only applies to choice types")