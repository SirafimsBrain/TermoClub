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


def test_control_symbols_are_mapped() -> None:
    """Ctrl+<символ> даёт тот же управляющий байт, что и в xterm."""
    assert TerminalKeymap.to_bytes("2", ctrl=True) == b"\x00"
    assert TerminalKeymap.to_bytes("Space", ctrl=True) == b"\x00"
    assert TerminalKeymap.to_bytes("[", ctrl=True) == b"\x1b"
    assert TerminalKeymap.to_bytes("6", ctrl=True) == b"\x1e"
    assert TerminalKeymap.to_bytes("\\", ctrl=True) == b"\x1c"
    assert TerminalKeymap.to_bytes("8", ctrl=True) == b"\x7f"
    assert TerminalKeymap.to_bytes("Backspace", ctrl=True) == b"\x17"
    # Неизвестная комбинация остаётся необработанной.
    assert TerminalKeymap.to_bytes("F13", ctrl=True) is None


def test_shift_and_control_modify_service_keys() -> None:
    """Shift+Tab, Ctrl+стрелки и Ctrl+Home/End дают xterm-последовательности."""
    assert TerminalKeymap.to_bytes("Tab", shift=True) == b"\x1b[Z"
    assert TerminalKeymap.to_bytes("Arrow Left", ctrl=True) == b"\x1b[1;5D"
    assert TerminalKeymap.to_bytes("Arrow Right", ctrl=True) == b"\x1b[1;5C"
    assert TerminalKeymap.to_bytes("Home", ctrl=True) == b"\x1b[1;5H"
    assert TerminalKeymap.to_bytes("End", ctrl=True) == b"\x1b[1;5F"
    assert TerminalKeymap.to_bytes("Delete", ctrl=True) == b"\x1b[3;5~"
    # Alt+Ctrl+<стрелка> — как и у букв, ESC плюс управляющая последовательность.
    assert TerminalKeymap.to_bytes("Arrow Up", ctrl=True, alt=True) == b"\x1b\x1b[1;5A"


def test_non_latin_key_label_does_not_crash() -> None:
    """Нелатинская метка клавиши не должна ронять раскладку.

    `Event.key` приходит из US-логики, но при нестандартной раскладке туда
    может попасть кириллица: `ord('ф') - 96` вылетает за диапазон байта.
    """
    assert TerminalKeymap.to_bytes("ф", ctrl=True) is None
    assert TerminalKeymap.to_bytes("я", ctrl=True, alt=True) is None
    assert TerminalKeymap.to_bytes("ß", meta=True) is None


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
