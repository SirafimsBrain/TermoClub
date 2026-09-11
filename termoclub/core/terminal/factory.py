# termoclub/core/terminal/factory.py
"""Фабрика контроллеров терминалов.

Создаёт нужную реализацию `TerminalController` по имени из конфига.
Новый терминал = реализация интерфейса + регистрация здесь.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.config import get_active_terminal

if TYPE_CHECKING:
    from core.terminal.base import TerminalController

logger = logging.getLogger(__name__)


def _ghostty() -> "TerminalController":
    from core.terminal.ghostty.controller import GhosttyController

    return GhosttyController()


def _kitty() -> "TerminalController":
    from core.terminal.kitty.controller import KittyController

    return KittyController()


_REGISTRY: dict[str, callable] = {
    "ghostty": _ghostty,  # реализация по умолчанию
    "kitty": _kitty,  # заготовка
}


def create_terminal_controller(name: str) -> "TerminalController":
    """Создаёт контроллер терминала по имени из реестра."""
    try:
        builder = _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Неизвестный терминал: {name!r}") from None
    return builder()


def get_terminal_controller() -> "TerminalController":
    """Возвращает контроллер активного терминала (из конфига)."""
    name = get_active_terminal()
    logger.info("Выбран терминал: %s", name)
    return create_terminal_controller(name)