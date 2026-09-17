# termoclub/core/sessions/terminal/TerminalPalette_test.py
"""Тесты палитры: имена/hex pyte -> цвета Flet."""
from __future__ import annotations

from core.sessions.terminal.TerminalPalette import (
    DEFAULT_BG,
    DEFAULT_FG,
    TerminalPalette,
)


def _palette() -> TerminalPalette:
    return TerminalPalette()


def test_named_ansi_colors() -> None:
    """Имена ANSI превращаются в hex-цвета."""
    palette = _palette()
    assert palette.foreground("red") == "#cd0000"
    assert palette.background("blue") == "#0000ee"
    assert palette.foreground("brightcyan") == "#55ffff"


def test_default_colors() -> None:
    """`default` и неизвестные значения дают цвета по умолчанию."""
    palette = _palette()
    assert palette.foreground("default") == DEFAULT_FG
    assert palette.background("default") == DEFAULT_BG
    assert palette.foreground("nonsense") == DEFAULT_FG
    assert palette.background("zzz") == DEFAULT_BG


def test_bold_brightens_base_color() -> None:
    """Жирный текст подсвечивает базовый цвет до bright-варианта."""
    palette = _palette()
    assert palette.foreground("green", bold=True) == "#55ff55"
    assert palette.foreground("green") == "#00cd00"
    # Уже bright-цвет жирным не меняется.
    assert palette.foreground("brightred", bold=True) == "#ff5555"


def test_hex_truecolor() -> None:
    """256/truecolor из pyte приходит как 6 hex-цифр."""
    palette = _palette()
    assert palette.foreground("ff8800") == "#ff8800"
    assert palette.background("00FF00") == "#00FF00"
    assert palette.foreground("12345") == DEFAULT_FG


def test_defaults_come_from_settings() -> None:
    """Палитра собирается из настроек: цвета по умолчанию настраиваются."""
    palette = TerminalPalette(foreground="#abcdef", background="#123456")
    assert palette.foreground("default") == "#abcdef"
    assert palette.background("default") == "#123456"
    # Именованные цвета ANSI остаются узнаваемыми.
    assert palette.foreground("red") == "#cd0000"
    assert palette.foreground_color == "#abcdef"
    assert palette.background_color == "#123456"


def test_ansi_overrides_are_merged() -> None:
    """Набор ANSI можно дополнить/переопределить из настроек."""
    palette = TerminalPalette(ansi={"red": "#ff0000", "custom": "#010203"})
    assert palette.foreground("red") == "#ff0000"
    assert palette.foreground("custom") == "#010203"
    assert palette.foreground("green") == "#00cd00"