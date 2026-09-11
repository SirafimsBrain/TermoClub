# termoclub/core/sessions/terminal/PyteScreen.py
"""Экран терминала на pyte: поток PTY -> сетка символов с атрибутами.

Класс отвечает только за эмуляцию (VT100/ANSI) и за доступ к экрану:
сетка ячеек, курсор, размер, UTF-8-декодирование с учётом границ чанков.
Отрисовку делает `TerminalView`, ввод — `TerminalKeymap`/`TextInputBridge`.
"""
from __future__ import annotations

import codecs
from collections.abc import Sequence

import pyte

#: Сколько строк истории держать (ещё не отображается, резерв под скроллбек).
DEFAULT_HISTORY = 1000


class PyteScreen:
    """Обёртка над `pyte.HistoryScreen` + `pyte.Stream`."""

    def __init__(
        self,
        columns: int = 80,
        lines: int = 24,
        history: int = DEFAULT_HISTORY,
    ) -> None:
        self._screen = pyte.HistoryScreen(columns, lines, history=history)
        self._stream = pyte.Stream(self._screen)
        # Инкрементальный декодер: многобайтовый символ может прийти
        # двумя чанками от PTY, наивный decode() дал бы «ромбики».
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    @property
    def columns(self) -> int:
        """Ширина экрана в символах."""
        return self._screen.columns

    @property
    def lines(self) -> int:
        """Высота экрана в строках."""
        return self._screen.lines

    @property
    def cursor(self) -> tuple[int, int] | None:
        """Позиция курсора (x, y) или None, если он скрыт (DECTCEM)."""
        if self._screen.cursor.hidden:
            return None
        return self._screen.cursor.x, self._screen.cursor.y

    def feed_bytes(self, chunk: bytes) -> None:
        """Скармливает экрану очередной чанк вывода PTY."""
        self.feed(self._decoder.decode(chunk))

    def feed(self, text: str) -> None:
        """Скармливает экрану готовый текст (тесты, служебные вставки)."""
        self._stream.feed(text)

    def resize(self, columns: int, lines: int) -> bool:
        """Меняет размер экрана. True, если размер действительно изменился."""
        if (columns, lines) == (self.columns, self.lines):
            return False
        self._screen.resize(lines=lines, columns=columns)
        return True

    def text(self) -> str:
        """Видимый экран как текст (для тестов, логов и отладки)."""
        return "\n".join(self._screen.display)

    def row(self, y: int) -> Sequence[pyte.screens.Char]:
        """Ячейки строки `y` (длиной `columns`, пустые — пробелы)."""
        buffer = self._screen.buffer[y]
        return [buffer[x] for x in range(self._screen.columns)]
