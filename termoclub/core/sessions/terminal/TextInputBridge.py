# termoclub/core/sessions/terminal/TextInputBridge.py
"""Мост текстового ввода: изменения скрытого поля Flet -> байты для PTY.

`page.on_keyboard_event` отдаёт только логическую метку клавиши
(`LogicalKeyboardKey.keyLabel`): латиницу в верхнем регистре, без учёта
раскладки и модификаторов. Настоящие символы (кириллица, регистр, AltGr,
dead keys, вставка из буфера) приходят только из `ft.TextField`, который
Flutter пропускает через IME. Поле отдаёт не нажатия, а новое значение
целиком, поэтому разницу считает этот класс.

Поле очищается сразу после отправки (см. `TerminalView.clear_input`),
поэтому события `on_change` относятся к двум разным состояниям поля:
устаревшему снимку (клиент ещё не получил нашу очистку и прислал значение
вместе с уже отправленным префиксом) и свежему вводу (очистка применена).
Различаются они по монотонности: если пришедшее значение — строгое
расширение последнего отправленного, это хвост устаревшего снимка, и его
префикс слать заново нельзя. Иначе быстрый набор («п», очистка, «р») ушёл
бы в PTY как «пр» при том, что «п» уже отправлена.

Строгое расширение (`len(value) > len(last_sent)`) не теряет и не
дублирует ввод: свежее значение, совпавшее с уже отправленным, означает,
что новых символов в поле нет, — а удаление и так уходит в PTY из
диспетчера клавиш (`Backspace` — не клавиша поля).
"""
from __future__ import annotations

#: Backspace в кодировке терминала (`\x7f`, как в xterm).
BACKSPACE = b"\x7f"


class TextInputBridge:
    """Превращает значения скрытого поля ввода в поток байт для PTY."""

    def __init__(self) -> None:
        self._mirror = ""
        self._last_sent = ""
        self._cleared = False

    @property
    def mirror(self) -> str:
        """Последнее обработанное значение поля."""
        return self._mirror

    def reset(self) -> None:
        """Забывает накопленное значение (например, после отправки строки).

        `_last_sent` при этом сохраняется: следующий снимок от клиента
        может быть сделан ещё до применения очистки, и без него повторно
        ушёл бы уже отправленный префикс.
        """
        self._mirror = ""
        self._cleared = True

    def feed(self, value: str) -> bytes:
        """Возвращает байты для PTY по новому значению поля.

        Поддерживаются дописывание, удаление (Backspace) и замена
        (выделение + ввод, IME-композиция): общий префикс сохраняется,
        удалённый хвост превращается в Backspace'ы, вставленный — в UTF-8.
        """
        previous, self._mirror = self._mirror, value
        if value == previous:
            return b""
        if not value and self._cleared:
            # Эхо нашей же очистки: пустое значение информации не несёт, но
            # ожидание устаревшего снимка снимать им нельзя.
            return b""
        cleared, self._cleared = self._cleared, False
        if cleared and self._last_sent and len(value) > len(self._last_sent):
            if value.startswith(self._last_sent):
                tail = value[len(self._last_sent) :]
                self._last_sent = value
                return tail.encode("utf-8")
        common = 0
        for index, (old, new) in enumerate(zip(previous, value)):
            if old != new:
                break
            common = index + 1
        self._last_sent = value
        if value.startswith(previous):
            return value[len(previous) :].encode("utf-8")
        removed = BACKSPACE * (len(previous) - common)
        return removed + value[common:].encode("utf-8")
