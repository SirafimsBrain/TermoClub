# termoclub/core/sessions/terminal/SmartCLIScreen.py
"""Экран smartcli-toolkit: адаптер `ScreenModel` под отрисовку `TerminalView`.

`TerminalView` рисует сетку по маленькому интерфейсу `PyteScreen`: `lines`,
`cursor` в виде `(x, y)`, `row(y)` со списком ячеек pyte и
`resize(columns, lines) -> bool`. `smartcli_core.ScreenModel` — другой
объект: курсор отдаётся как `(row, column)`, а `row_cells()` возвращает
урезанный `CellAttrs` (только `data`/`fg`/`bg`/`bold`/`reverse`, без
курсива, подчёркивания и зачёркивания). Поэтому между ними нужен
переходник, а не подмена одного другим.

`feed_bytes()` намеренно ничего не делает. Байты в модель уже положил
`PtySession.pump()` — он же отвечает на DSR/DA-запросы программы
(`ESC[6n` / `ESC[c`). Если скормить чанк ещё раз, каждый байт
обрабатывался бы дважды: управляющие последовательности срабатывали бы
повторно, а состояние pyte уезжало бы. Экран — только чтение.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import pyte


class _Cell(NamedTuple):
    """Ячейка строки в форме, которую читает `TerminalView`.

    Запасной путь отрисовки: `CellAttrs` из smartcli урезан (нет `italics`,
    `underscore` и `strikethrough`), поэтому здесь они всегда выключены.
    """

    data: str
    fg: str
    bg: str
    bold: bool
    reverse: bool
    italics: bool = False
    underscore: bool = False
    strikethrough: bool = False


class SmartCLIScreen:
    """Только чтение: адаптер над живой `smartcli_core.ScreenModel`."""

    def __init__(self, model) -> None:  # noqa: ANN001 — smartcli_core.ScreenModel
        self._model = model

    @property
    def columns(self) -> int:
        """Ширина экрана в символах."""
        return self._model.cols

    @property
    def lines(self) -> int:
        """Высота экрана в строках."""
        return self._model.rows

    @property
    def cursor(self) -> tuple[int, int] | None:
        """Позиция курсора (x, y) или None, если он скрыт (DECTCEM)."""
        if self._model.cursor_hidden:
            return None
        row, column = self._model.cursor
        return column, row

    def feed_bytes(self, chunk: bytes) -> None:
        """Ничего не делает: чанк уже скармливает `PtySession.pump()`.

        Повторное кормление ломало бы эмуляцию (см. docstring модуля), а
        отрисовке нужен только сам факт нового вывода.
        """

    def resize(self, columns: int, lines: int) -> bool:
        """Меняет размер экрана. True, если размер действительно изменился."""
        if (columns, lines) == (self.columns, self.lines):
            return False
        self._model.resize(columns, lines)
        return True

    def text(self) -> str:
        """Видимый экран как текст (для тестов, логов и отладки)."""
        return self._model.text()

    def visible_text(self) -> str:
        """Видимый экран без пустых полей — то, что имеет смысл копировать.

        У каждой строки срезаются правые пробелы (в терминале строка
        добивается ими до ширины экрана), а пустые строки снизу отбрасываются.
        """
        lines = [line.rstrip() for line in self._model.display]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def row(self, y: int) -> Sequence[pyte.screens.Char | _Cell]:
        """Ячейки строки `y` (длиной `columns`, пустые — пробелы).

        Берём буфер pyte напрямую: `CellAttrs` из smartcli теряет начертания
        (`italics`/`underscore`/`strikethrough`), а `TerminalView` рисует их
        в спанах. `row_cells()` к тому же строит новый NamedTuple на каждую
        ячейку — на 80x24 это лишние 1920 объектов на кадр.

        `ScreenModel.screen` — деталь реализации smartcli, а не её публичный
        контракт. Если апстрим её переименует или спрячет, отрисовка перейдёт
        на `row_cells()` (без курсива и подчёркивания) вместо падения.
        """
        screen = getattr(self._model, "screen", None)
        if screen is not None and hasattr(screen, "buffer"):
            row = screen.buffer[y]
            return [row[x] for x in range(screen.columns)]
        return [_Cell(*cell) for cell in self._model.row_cells(y)]
