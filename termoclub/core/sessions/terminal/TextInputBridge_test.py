# termoclub/core/sessions/terminal/TextInputBridge_test.py
"""Тесты моста текстового ввода (скрытое поле Flet -> байты PTY)."""
from __future__ import annotations

from core.sessions.terminal.TextInputBridge import TextInputBridge


def test_cyrillic_and_case_survive() -> None:
    """Кириллица и регистр доходят до PTY без изменений."""
    bridge = TextInputBridge()
    assert bridge.feed("привет") == "привет".encode("utf-8")
    bridge.reset()
    assert bridge.feed("Hello") == b"Hello"


def test_appending_sends_only_the_delta() -> None:
    """При дописывании отправляется только новый хвост."""
    bridge = TextInputBridge()
    assert bridge.feed("ab") == b"ab"
    assert bridge.feed("abc") == b"c"
    assert bridge.mirror == "abc"


def test_deletion_becomes_backspaces() -> None:
    """Удаление хвоста превращается в Backspace'ы."""
    bridge = TextInputBridge()
    bridge.feed("abc")
    assert bridge.feed("a") == b"\x7f\x7f"
    assert bridge.feed("") == b"\x7f"


def test_replacement_keeps_common_prefix() -> None:
    """Замена (выделение + ввод) считает общий префикс."""
    bridge = TextInputBridge()
    bridge.feed("hello")
    assert bridge.feed("help") == b"\x7f\x7fp"


def test_repeated_value_is_ignored() -> None:
    """То же значение не порождает байт (защита от дублей)."""
    bridge = TextInputBridge()
    bridge.feed("same")
    assert bridge.feed("same") == b""


def test_reset_forgets_mirror() -> None:
    """reset() очищает накопленное значение (после отправки строки)."""
    bridge = TextInputBridge()
    bridge.feed("cmd")
    bridge.reset()
    assert bridge.mirror == ""
    assert bridge.feed("cmd") == b"cmd"
