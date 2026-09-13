# termoclub/core/sessions/terminal/TerminalKeymap_test.py
"""Тесты раскладки терминала: клавиша Flet -> байты PTY."""
from __future__ import annotations

from core.sessions.terminal.TerminalKeymap import TerminalKeymap


def test_special_keys() -> None:
    """Служебные клавиши маппятся в escape-последовательности xterm."""
    assert TerminalKeymap.to_bytes("Enter") == b"\r"
    assert TerminalKeymap.to_bytes("Backspace") == b"\x7f"
    assert TerminalKeymap.to_bytes("Tab") == b"\t"
    assert TerminalKeymap.to_bytes("Escape") == b"\x1b"
    assert TerminalKeymap.to_bytes("Arrow Up") == b"\x1b[A"
    assert TerminalKeymap.to_bytes("Arrow Left") == b"\x1b[D"
    assert TerminalKeymap.to_bytes("Delete") == b"\x1b[3~"
    assert TerminalKeymap.to_bytes("Page Down") == b"\x1b[6~"
    assert TerminalKeymap.to_bytes("F5") == b"\x1b[15~"
    assert TerminalKeymap.to_bytes(" ") == b" "


def test_control_and_alt_combinations() -> None:
    """Ctrl+<буква> и Alt+<символ> дают управляющие последовательности."""
    assert TerminalKeymap.to_bytes("c", ctrl=True) == b"\x03"
    assert TerminalKeymap.to_bytes("C", ctrl=True) == b"\x03"
    assert TerminalKeymap.to_bytes("d", meta=True) == b"\x04"
    assert TerminalKeymap.to_bytes("x", alt=True) == b"\x1bx"
    # Alt+Ctrl+<буква> — это ESC плюс управляющий байт (как в xterm).
    assert TerminalKeymap.to_bytes("c", ctrl=True, alt=True) == b"\x1b\x03"
    assert TerminalKeymap.to_bytes("2", ctrl=True) is None


def test_printable_keys_and_modifiers() -> None:
    """Печатаемые клавиши отдаются как есть, модификаторы байт не дают."""
    # Печатаемые символы без модификаторов обрабатываются полем ввода, поэтому keymap возвращает None
    assert TerminalKeymap.to_bytes("a") is None
    assert TerminalKeymap.to_bytes("1") is None
    assert TerminalKeymap.to_bytes("Shift") is None
    assert TerminalKeymap.to_bytes("Control") is None
    assert TerminalKeymap.to_bytes("Unknown Key") is None
    assert TerminalKeymap.is_modifier("Meta") is True
    assert TerminalKeymap.is_modifier("a") is False
