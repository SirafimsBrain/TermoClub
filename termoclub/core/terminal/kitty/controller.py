# termoclub/core/terminal/kitty/controller.py
"""Заготовка контроллера Kitty.

Планируется через remote control: `kitty @ new-window` / `kitty @ new-tab`.
"""
from __future__ import annotations

import logging
from typing import Any

from core.result import Result
from core.terminal.base import TerminalController

logger = logging.getLogger(__name__)


class KittyController(TerminalController):
    """Заглушка под Kitty: все операции возвращают «не реализовано»."""

    def open_new_window(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        logger.warning("Kitty: open_new_window не реализован")
        return Result.failure("Kitty: open_new_window пока не реализован")

    def open_new_tab(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        logger.warning("Kitty: open_new_tab не реализован")
        return Result.failure("Kitty: open_new_tab пока не реализован")

    def focus(self) -> Result:
        logger.warning("Kitty: focus не реализован")
        return Result.failure("Kitty: focus пока не реализован")