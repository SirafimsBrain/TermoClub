# termoclub/core/settings/Choice.py
"""Вариант значения для настроек типов CHOICE и MULTI_CHOICE."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    """Пара «значение — подпись» из схемы настроек."""

    value: str
    label: str

    @classmethod
    def from_dict(cls, payload: dict) -> "Choice":
        """Строит вариант из JSON-объекта схемы.

        Пустая строка — допустимое значение: так в схемах выражается
        «системное умолчание» (шрифт, каталог, оболочка).
        """
        if not isinstance(payload, dict) or "value" not in payload:
            raise ValueError(f"choice without a 'value': {payload!r}")
        value = payload["value"]
        if not isinstance(value, str):
            raise ValueError(f"choice value must be a string: {payload!r}")
        label = payload.get("label")
        return cls(value=value, label=label if isinstance(label, str) else value)