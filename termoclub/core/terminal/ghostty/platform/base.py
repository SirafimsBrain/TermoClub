# termoclub/core/terminal/ghostty/platform/base.py
"""Абстрактный интерфейс платформенного уровня Ghostty."""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.result import Result


class GhosttyPlatform(ABC):
    """Платформенная реализация управления Ghostty (macOS / Linux)."""

    @abstractmethod
    def open_new_window(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        """Открывает новое окно Ghostty."""

    @abstractmethod
    def open_new_tab(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        """Открывает новую вкладку Ghostty."""

    @abstractmethod
    def focus(self) -> Result:
        """Переводит фокус на Ghostty."""