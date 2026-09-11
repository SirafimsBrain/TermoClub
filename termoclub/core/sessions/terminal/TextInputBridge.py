# termoclub/core/sessions/terminal/TextInputBridge.py
"""Мост текстового ввода: изменения скрытого поля Flet -> байты для PTY.

`page.on_keyboard_event` отдаёт только логическую метку клавиши
(`LogicalKeyboardKey.keyLabel`): латиницу в верхнем регистре, без учёта
раскладки и модификаторов. Настоящие символы (кириллица, регистр, AltGr,
dead keys, вставка из буфера) приходят только из `ft.TextField`, который
Flutter пропускает через IME. Поле отдаёт не нажатия, а новое значение
целиком, поэтому разницу считает этот класс.
"""
from __future__ import annotations

#: Backspace в кодировке терминала (`\x7f`, как в xterm).
BACKSPACE = b"\x7f"


class TextInputBridge:
    """Превращает значения скрытого поля ввода в поток байт для PTY."""

    def __init__(self) -> None:
        self._mirror = ""

    @property
    def mirror(self) -> str:
        """Последнее обработанное значение поля."""
        return self._mirror

    def reset(self) -> None:
        """Забывает накопленное значение (например, после отправки строки)."""
        self._mirror = ""

    def feed(self, value: str) -> bytes:
        """Возвращает байты для PTY по новому значению поля.

        Поддерживаются дописывание, удаление (Backspace) и замена
        (выделение + ввод, IME-композиция): общий префикс сохраняется,
        удалённый хвост превращается в Backspace'ы, вставленный — в UTF-8.
        """
        previous, self._mirror = self._mirror, value
        if value == previous:
            return b""
        if value.startswith(previous):
            return value[len(previous) :].encode("utf-8")
        common = 0
        for index, (old, new) in enumerate(zip(previous, value)):
            if old != new:
                break
            common = index + 1
        removed = BACKSPACE * (len(previous) - common)
        return removed + value[common:].encode("utf-8")
