# ghostty_wrapper/core/events.py
"""Заготовка под события внутри терминалов (цвет вкладок и т.д.)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TerminalEvents:
    """Точка расширения для реакций на события в терминале."""

    def __init__(self) -> None:
        self._tab_color_listeners: list[callable] = []

    def on_tab_color_changed(self, listener: callable) -> None:
        """Регистрирует обработчик изменения цвета вкладки."""
        self._tab_color_listeners.append(listener)

    def emit_tab_color_changed(self, session_id: str, color: str) -> None:
        """Уведомляет подписчиков об изменении цвета вкладки."""
        logger.info("Цвет вкладки %s изменён на %s", session_id, color)
        for listener in self._tab_color_listeners:
            listener(session_id, color)


events = TerminalEvents()