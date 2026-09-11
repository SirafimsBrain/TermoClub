# ghostty_wrapper/core/config.py
"""Конфигурация TermoClub: какой терминал активен по умолчанию."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_TERMINAL = "ghostty"

_SUPPORTED = {"ghostty", "kitty"}


def get_active_terminal() -> str:
    """Возвращает имя активного терминала (переменная TERMOCLUB_TERMINAL)."""
    name = os.environ.get("TERMOCLUB_TERMINAL", DEFAULT_TERMINAL).strip().lower()
    if name not in _SUPPORTED:
        logger.warning(
            "Неизвестный терминал %r, используется %r", name, DEFAULT_TERMINAL
        )
        return DEFAULT_TERMINAL
    return name


def get_active_terminal_name() -> str:
    """Человекочитаемое имя активного терминала."""
    return get_active_terminal()