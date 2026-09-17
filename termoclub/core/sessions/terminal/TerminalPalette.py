# termoclub/core/sessions/terminal/TerminalPalette.py
"""Палитра терминала: имена/hex из pyte -> цвета Flet.

pyte отдаёт в `Char.fg`/`Char.bg` либо имя (`default`, `red`, `brightgreen`,
...), либо строку из 6 hex-цифр для 256/truecolor. Здесь они превращаются в
цвета Flet. Жирный шрифт, по конвенции терминалов, не утолщается, а
«подсвечивает» базовый цвет до bright-варианта — так не съезжает сетка
моноширинного шрифта.

Палитра — объект, а не набор констант: цвета по умолчанию и ANSI-набор
приходят из настроек (`terminal-pyte` / `terminal-smartcli`), поэтому у
каждой вкладки терминала может быть своя палитра.
"""
from __future__ import annotations

from collections.abc import Mapping

#: Цвет по умолчанию для текста (умолчание схемы настроек).
DEFAULT_FG = "#d8dee9"

#: Цвет фона терминала (умолчание схемы настроек).
DEFAULT_BG = "#000000"

#: ANSI-цвета (xterm-подобные, читаемые на чёрном фоне).
ANSI = {
    "black": "#000000",
    "red": "#cd0000",
    "green": "#00cd00",
    "brown": "#cdcd00",
    "yellow": "#cdcd00",
    "blue": "#0000ee",
    "magenta": "#cd00cd",
    "cyan": "#00cdcd",
    "white": "#e5e5e5",
    "brightblack": "#7f7f7f",
    "brightred": "#ff5555",
    "brightgreen": "#55ff55",
    "brightbrown": "#ffff55",
    "brightyellow": "#ffff55",
    "brightblue": "#5c5cff",
    "brightmagenta": "#ff55ff",
    "brightcyan": "#55ffff",
    "brightwhite": "#ffffff",
}

#: Базовый цвет -> bright-вариант (используется для атрибута bold).
BRIGHT = {
    "black": "brightblack",
    "red": "brightred",
    "green": "brightgreen",
    "brown": "brightbrown",
    "yellow": "brightyellow",
    "blue": "brightblue",
    "magenta": "brightmagenta",
    "cyan": "brightcyan",
    "white": "brightwhite",
}


class TerminalPalette:
    """Преобразование цветов pyte в цвета Flet с настраиваемыми умолчаниями."""

    def __init__(
        self,
        foreground: str = DEFAULT_FG,
        background: str = DEFAULT_BG,
        ansi: Mapping[str, str] | None = None,
    ) -> None:
        self._foreground = foreground or DEFAULT_FG
        self._background = background or DEFAULT_BG
        self._ansi = {**ANSI, **(ansi or {})}

    @property
    def foreground_color(self) -> str:
        """Цвет текста по умолчанию (`default` в pyte)."""
        return self._foreground

    @property
    def background_color(self) -> str:
        """Цвет фона по умолчанию."""
        return self._background

    def resolve(self, color: str, fallback: str) -> str:
        """Имя ANSI или hex-строка pyte -> `#RRGGBB`."""
        if color in self._ansi:
            return self._ansi[color]
        if len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color):
            return f"#{color}"
        return fallback

    def foreground(self, color: str, bold: bool = False) -> str:
        """Цвет текста; `bold` подсвечивает базовые цвета до bright."""
        if bold and color in BRIGHT:
            return self.resolve(BRIGHT[color], self._foreground)
        return self.resolve(color, self._foreground)

    def background(self, color: str) -> str:
        """Цвет фона ячейки."""
        return self.resolve(color, self._background)