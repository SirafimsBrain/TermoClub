# ghostty_wrapper/core/terminal/generic_test.py
"""Тесты: фабрика, единый результат и неизвестный терминал."""
from __future__ import annotations

import pytest

from core.config import get_active_terminal
from core.terminal.base import TerminalController
from core.terminal.factory import create_terminal_controller, get_terminal_controller


def test_factory_ghostty() -> None:
    """Фабрика создаёт Ghostty-контроллер."""
    ctrl = create_terminal_controller("ghostty")
    assert isinstance(ctrl, TerminalController)


def test_factory_kitty() -> None:
    """Фабрика создаёт Kitty-контроллер (заглушку)."""
    ctrl = create_terminal_controller("kitty")
    assert isinstance(ctrl, TerminalController)


def test_factory_unknown_raises() -> None:
    """Неизвестный терминал вызывает ValueError."""
    with pytest.raises(ValueError):
        create_terminal_controller("nonexistent")


def test_active_terminal_is_ghostty() -> None:
    """Активным терминалом по умолчанию является ghostty."""
    assert get_active_terminal() == "ghostty"