# termoclub/core/terminal/base.py
"""Стандартизированный интерфейс контроллера терминала.

Это единственный контракт, который знает UI и остальная бизнес-логика.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.result import Result


class TerminalController(ABC):
    """Абстрактный контроллер терминала.

    Реализации живут в `core/terminal/<term>/` и возвращают результат
    всегда в едином формате `core.result.Result`.
    """

    @abstractmethod
    def open_new_window(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        """Открывает новое окно терминала."""

    @abstractmethod
    def open_new_tab(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        """Открывает новую вкладку терминала (обязательная часть контракта)."""

    @abstractmethod
    def focus(self) -> Result:
        """Переводит фокус на терминал."""