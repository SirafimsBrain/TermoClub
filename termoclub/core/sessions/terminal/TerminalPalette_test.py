# termoclub/core/sessions/terminal/TerminalPalette_test.py
"""Тесты палитры: имена/hex pyte -> цвета Flet."""
from __future__ import annotations

from core.sessions.terminal.TerminalPalette import (
    DEFAULT_BG,
    DEFAULT_FG,
    TerminalPalette,
)


def test_named_ansi_colors() -> None:
    """Имена ANSI превращаются в hex-цвета."""
    assert TerminalPalette.foreground("red") == "#cd0000"
    assert TerminalPalette.background("blue") == "#0000ee"
    assert TerminalPalette.foreground("brightcyan") == "#55ffff"


def test_default_colors() -> None:
    """`default` и неизвестные значения дают цвета по умолчанию."""
    assert TerminalPalette.foreground("default") == DEFAULT_FG
    assert TerminalPalette.background("default") == DEFAULT_BG
    assert TerminalPalette.foreground("nonsense") == DEFAULT_FG
    assert TerminalPalette.background("zzz") == DEFAULT_BG


def test_bold_brightens_base_color() -> None:
    """Жирный текст подсвечивает базовый цвет до bright-варианта."""
    assert TerminalPalette.foreground("green", bold=True) == "#55ff55"
    assert TerminalPalette.foreground("green") == "#00cd00"
    # Уже bright-цвет жирным не меняется.
    assert TerminalPalette.foreground("brightred", bold=True) == "#ff5555"


def test_hex_truecolor() -> None:
    """256/truecolor из pyte приходит как 6 hex-цифр."""
    assert TerminalPalette.foreground("ff8800") == "#ff8800"
    assert TerminalPalette.background("00FF00") == "#00FF00"
    assert TerminalPalette.foreground("12345") == DEFAULT_FG
