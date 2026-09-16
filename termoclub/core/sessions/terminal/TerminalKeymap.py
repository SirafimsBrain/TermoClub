# termoclub/core/sessions/terminal/TerminalKeymap.py
"""Раскладка клавиатуры: служебная клавиша Flet -> байты для PTY.

Flet отдаёт в `KeyboardEvent.key` только `LogicalKeyboardKey.keyLabel` —
логическую (US) метку клавиши в верхнем регистре, без учёта раскладки и
модификаторов. Поэтому здесь маппятся только служебные клавиши и
управляющие комбинации; печатаемые символы приходят из скрытого поля
ввода (см. `TextInputBridge`).
"""
from __future__ import annotations

#: Модификаторы: сами по себе байт не порождают.
MODIFIER_ONLY = frozenset(
    {
        "Shift",
        "Control",
        "Alt",
        "Meta",
        "Caps Lock",
        "Num Lock",
        "Scroll Lock",
        "Insert",
    }
)

#: Служебные клавиши в кодировках VT/xterm.
SPECIALS = {
    "Enter": b"\r",
    "Backspace": b"\x7f",
    "Tab": b"\t",
    "Escape": b"\x1b",
    "Delete": b"\x1b[3~",
    "Home": b"\x1b[H",
    "End": b"\x1b[F",
    "Page Up": b"\x1b[5~",
    "Page Down": b"\x1b[6~",
    "Arrow Up": b"\x1b[A",
    "Arrow Down": b"\x1b[B",
    "Arrow Right": b"\x1b[C",
    "Arrow Left": b"\x1b[D",
    " ": b" ",
    "Space": b" ",
    "F1": b"\x1bOP",
    "F2": b"\x1bOQ",
    "F3": b"\x1bOR",
    "F4": b"\x1bOS",
    "F5": b"\x1b[15~",
    "F6": b"\x1b[17~",
    "F7": b"\x1b[18~",
    "F8": b"\x1b[19~",
    "F9": b"\x1b[20~",
    "F10": b"\x1b[21~",
    "F11": b"\x1b[23~",
    "F12": b"\x1b[24~",
}

#: `Shift`-версии служебных клавиш (метка от Shift не зависит).
SHIFTED = {
    "Tab": b"\x1b[Z",  # back-tab
}

#: `Ctrl` (и `Alt`) поверх служебных клавиш: `1;5` — модификатор Ctrl.
CTRL_SPECIALS = {
    "Arrow Up": b"\x1b[1;5A",
    "Arrow Down": b"\x1b[1;5B",
    "Arrow Right": b"\x1b[1;5C",
    "Arrow Left": b"\x1b[1;5D",
    "Home": b"\x1b[1;5H",
    "End": b"\x1b[1;5F",
    "Delete": b"\x1b[3;5~",
    # Интерактивный `bash` (readline) трактует это как «стереть слово».
    "Backspace": b"\x17",
}

#: `Ctrl` + символ в US-раскладке -> управляющий байт (как в xterm).
CTRL_SYMBOLS = {
    " ": b"\x00",
    "@": b"\x00",
    "2": b"\x00",
    "[": b"\x1b",
    "3": b"\x1b",
    "\\": b"\x1c",
    "4": b"\x1c",
    "]": b"\x1d",
    "5": b"\x1d",
    "^": b"\x1e",
    "6": b"\x1e",
    "_": b"\x1f",
    "-": b"\x1f",
    "/": b"\x1f",
    "7": b"\x1f",
    "8": b"\x7f",
    "Space": b"\x00",
    "Backspace": b"\x17",
}


class TerminalKeymap:
    """Переводит служебные клавиши и комбинации в байты терминала."""

    @staticmethod
    def is_modifier(key: str) -> bool:
        """True для клавиш-модификаторов (Shift, Ctrl, ...)."""
        return key in MODIFIER_ONLY

    @staticmethod
    def to_bytes(
        key: str,
        shift: bool = False,
        ctrl: bool = False,
        alt: bool = False,
        meta: bool = False,
    ) -> bytes | None:
        """Возвращает байты для PTY или None, если клавиша не наша.

        `Ctrl+C` -> `0x03`, `Ctrl+Space` -> `0x00`, `Ctrl+Arrow Left` ->
        `ESC[1;5D`, `Alt+x` -> `ESC x`, стрелки/`F-клавиши` -> их
        escape-последовательности. Печатаемые символы без модификаторов
        сюда не относятся: их отдаёт поле ввода с учётом раскладки.
        """
        if TerminalKeymap.is_modifier(key):
            return None
        if ctrl or meta:
            data = TerminalKeymap._control_bytes(key, alt=alt)
            return data
        if alt and len(key) == 1:
            return b"\x1b" + key.encode("utf-8", errors="ignore")
        if shift and key in SHIFTED:
            return SHIFTED[key]
        if key in SPECIALS:
            return SPECIALS[key]
        return None

    @staticmethod
    def _control_bytes(key: str, alt: bool = False) -> bytes | None:
        """`Ctrl+<клавиша>` -> управляющий байт (или None).

        Метка приходит из US-раскладки, поэтому таблицы хватает; латиница
        считается арифметикой (`Ctrl+A` -> `0x01`), а нелатинская метка
        отбрасывается — иначе `ord()` вылетел бы за диапазон байта.
        """
        if key.isascii() and len(key) == 1 and key.isalpha():
            code = bytes([ord(key.lower()) - 96])
            return b"\x1b" + code if alt else code
        if key in CTRL_SPECIALS:
            code = CTRL_SPECIALS[key]
            return b"\x1b" + code if alt else code
        if key in CTRL_SYMBOLS:
            code = CTRL_SYMBOLS[key]
            return b"\x1b" + code if alt else code
        return None
