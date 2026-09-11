# ghostty_wrapper/core/result.py
"""Единый формат результата вызовов контроллера терминала."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    """Результат операции: успех/ошибка + человекочитаемое сообщение."""

    ok: bool
    message: str

    @classmethod
    def success(cls, message: str = "OK") -> "Result":
        """Возвращает успешный результат."""
        return cls(ok=True, message=message)

    @classmethod
    def failure(cls, message: str) -> "Result":
        """Возвращает результат-ошибку."""
        return cls(ok=False, message=message)