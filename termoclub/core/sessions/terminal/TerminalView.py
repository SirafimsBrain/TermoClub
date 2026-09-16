# termoclub/core/sessions/terminal/TerminalView.py
"""Flet-сторона pyte-терминала: отрисовка экрана и скрытое поле ввода.

Класс — «тупое» представление: он не знает ни про PTY, ни про сессии.
Он собирает контролы, превращает экран `PyteScreen` в спаны `ft.Text`
(цвета ANSI, атрибуты, курсор) и отдаёт наружу уже готовые события:

* `on_bytes(bytes)` — текст, набранный в скрытом поле (через IME Flutter),
  и `Enter` из него;
* `on_resize(columns, lines)` — новый размер терминала в символах;
* `on_focus_request()` — пользователь кликнул по терминалу.

Терминал — **сетка фиксированного размера, а не прокручиваемый список**.
Скроллбек живёт внутри pyte, а видимая область обязана ровно совпадать с
размером контейнера: иначе контент переполняет вьюпорт, появляется полоса
прокрутки, и экран «уезжает» вниз (видны только пустые строки под
приглашением). Поэтому всем спанам, включая переводы строк, задаётся один
и тот же `TextStyle.height`, а число строк считается по нему же — размер
отрисовки совпадает с размером контейнера с точностью до пикселя.

Отдельное скрытое `ft.TextField` нужно потому, что Flet в
`page.on_keyboard_event` отдаёт только логические метки клавиш
(латиница в верхнем регистре без раскладки) — настоящие символы, вставку
из буфера и IME умеет только поле ввода. Событие клавиатуры Flet получает
глобальным `HardwareKeyboard.addHandler` (см. `page.dart`), поэтому оно
приходит и когда поле в фокусе: сессия отличает «печатаемые» клавиши поля
от служебных по `input_focused`.
"""
from __future__ import annotations

from collections.abc import Callable

import flet as ft

from core.sessions.terminal.PyteScreen import PyteScreen
from core.sessions.terminal.TerminalPalette import DEFAULT_BG, DEFAULT_FG, TerminalPalette
from core.sessions.terminal.TextInputBridge import TextInputBridge

#: Моноширинный шрифт из локальных assets (`FontAwesome.FONTS`).
MONO_FONT = "JetBrains Mono"

#: Доля ширины знакоместа от кегля (JetBrains Mono — 0.6em).
MONO_ASPECT = 0.6

#: Высота строки как множитель кегля (`TextStyle.height`).
MONO_LINE_HEIGHT = 1.25

#: Запас по колонкам на погрешность ширины знакоместа (см. `grid_size`).
GRID_COLUMN_SLACK = 1

#: Граница скрытого поля ввода. В Flet 1.0 `InputBorder.NONE` объявлен
#: устаревшим, а его замена (`NoInputBorder`) в 0.86 ещё не существует.
INPUT_BORDER = (
    ft.NoInputBorder() if hasattr(ft, "NoInputBorder") else ft.InputBorder.NONE
)

#: Атрибуты пустой ячейки: (fg, bg, italics, underscore, strikethrough).
BLANK = (DEFAULT_FG, DEFAULT_BG, False, False, False)

#: Ограничение кеша стилей (truecolor может плодить цвета бесконечно).
STYLE_CACHE_LIMIT = 512


class TerminalView:
    """Контролы терминала и преобразование экрана pyte в спаны Flet."""

    def __init__(
        self,
        on_bytes: Callable[[bytes], None],
        on_resize: Callable[[int, int], None] | None = None,
        on_focus_request: Callable[[], None] | None = None,
        *,
        font_family: str = MONO_FONT,
        font_size: int = 13,
        padding: int = 8,
        min_columns: int = 20,
        min_lines: int = 4,
    ) -> None:
        self._on_bytes = on_bytes
        self._on_resize = on_resize
        self._on_focus_request = on_focus_request
        self._font_family = font_family
        self._font_size = font_size
        self._padding = padding
        self._min_columns = min_columns
        self._min_lines = min_lines
        self._char_width = max(1.0, font_size * MONO_ASPECT)
        self._line_height = max(1.0, font_size * MONO_LINE_HEIGHT)
        self._input_bridge = TextInputBridge()
        self._styles: dict[tuple, ft.TextStyle] = {}
        self._size: tuple[int, int] | None = None
        self._input_focused = False
        self._text: ft.Text | None = None
        self._input: ft.TextField | None = None
        self._control: ft.Container | None = None

    # --- Контролы ---

    @property
    def input_ready(self) -> bool:
        """True, когда скрытое поле ввода уже смонтировано в дереве."""
        return self._input is not None

    @property
    def input_focused(self) -> bool:
        """True, пока клавиатурный фокус в скрытом поле ввода.

        Пока поле в фокусе, печатаемые символы приходят из его IME-значения
        (кириллица, регистр), а `KeyboardEvent` отдаёт те же клавиши
        повторно — их надо игнорировать. Пока фокуса нет, те же символы
        приходится брать из диспетчера (латиница, US-раскладка): терять ввод
        хуже, чем вводить его без кириллицы.
        """
        return self._input_focused

    @property
    def size(self) -> tuple[int, int] | None:
        """Последняя разосланная сетка (колонки, строки) или None."""
        return self._size

    @property
    def control(self) -> ft.Control:
        """Строит (один раз) контейнер терминала с экраном и полем ввода."""
        if self._control is None:
            self._text = ft.Text(
                value="",
                font_family=self._font_family,
                size=self._font_size,
                style=ft.TextStyle(height=MONO_LINE_HEIGHT),
                no_wrap=True,
                spans=[ft.TextSpan(text=" ", style=self._style(BLANK))],
            )
            self._input = ft.TextField(
                value="",
                width=1,
                height=1,
                opacity=0,
                text_size=1,
                content_padding=0,
                border=INPUT_BORDER,
                cursor_color=ft.Colors.TRANSPARENT,
                autofocus=True,
                on_change=self._on_field_change,
                on_submit=self._on_field_submit,
                on_focus=self._on_field_focus,
                on_blur=self._on_field_blur,
            )
            self._control = ft.Container(
                bgcolor=DEFAULT_BG,
                padding=self._padding,
                expand=True,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                on_size_change=self._on_size_change,
                on_click=self._on_click,
                content=ft.Stack(
                    expand=True,
                    fit=ft.StackFit.LOOSE,
                    controls=[self._text, self._input],
                ),
            )
        return self._control

    # --- Экран ---

    def render(self, screen: PyteScreen) -> None:
        """Перерисовывает экран терминала."""
        if self._text is None:
            return
        self._text.spans = self.spans(screen)
        try:
            self._text.update()
        except RuntimeError:
            pass  # Контрол ещё не примонтирован к странице.

    def spans(self, screen: PyteScreen) -> list[ft.TextSpan]:
        """Строит спаны экрана: цветные «прогоны» ячеек и блок курсора.

        Строк получается ровно `screen.lines`: переводы строк задаются
        спанами с тем же `height`, поэтому высота отрисовки предсказуема.
        """
        cursor = screen.cursor
        spans: list[ft.TextSpan] = []
        for y in range(screen.lines):
            if y:
                spans.append(ft.TextSpan(text="\n", style=self._style(BLANK)))
            cells = screen.row(y)
            specs = [self.spec(cell) for cell in cells]
            limit = len(specs)
            # Хвост из пустых ячеек не рисуем: атрибуты по умолчанию есть и у
            # обычных букв, поэтому проверяем ещё и символ (пробел).
            while limit and specs[limit - 1] == BLANK and cells[limit - 1].data == " ":
                limit -= 1
            if cursor is not None and cursor[1] == y:
                x = max(0, min(cursor[0], len(specs) - 1))
                specs = self._with_cursor(specs, x)
                limit = max(limit, x + 1)
            self._append_runs(spans, cells, specs, limit)
        return spans or [ft.TextSpan(text=" ", style=self._style(BLANK))]

    @staticmethod
    def spec(cell) -> tuple:  # noqa: ANN001 — pyte.screens.Char
        """Атрибуты ячейки: (fg, bg, italics, underscore, strikethrough)."""
        fg = TerminalPalette.foreground(cell.fg, cell.bold)
        bg = TerminalPalette.background(cell.bg)
        if cell.reverse:
            fg, bg = bg, fg
        return (fg, bg, cell.italics, cell.underscore, cell.strikethrough)

    @staticmethod
    def _with_cursor(specs: list[tuple], x: int) -> list[tuple]:
        """Инвертирует цвета ячейки под курсором (блочный курсор)."""
        fg, bg, *_ = specs[x]
        specs[x] = (bg, fg, False, False, False)
        return specs

    def _append_runs(
        self,
        spans: list[ft.TextSpan],
        cells,  # noqa: ANN001 — pyte.screens.Char
        specs: list[tuple],
        limit: int,
    ) -> None:
        """Склеивает соседние ячейки с одинаковыми атрибутами в один спан."""
        index = 0
        while index < limit:
            end = index + 1
            while end < limit and specs[end] == specs[index]:
                end += 1
            text = "".join(cells[i].data for i in range(index, end))
            if text:
                spans.append(ft.TextSpan(text=text, style=self._style(specs[index])))
            index = end

    def _style(self, spec: tuple) -> ft.TextStyle:
        """Стиль Flet для набора атрибутов (с кешем, чтобы не плодить объекты).

        Шрифт, кегль и `height` задаются явно у каждого спана: переводы строк
        и любые «бесстилевые» вставки не должны получать другую высоту
        строки, иначе сетка съезжает и отрисовка перестаёт влезать в контейнер.
        """
        style = self._styles.get(spec)
        if style is not None:
            return style
        fg, bg, italics, underscore, strikethrough = spec
        decoration = None
        if underscore and strikethrough:
            decoration = ft.TextDecoration.UNDERLINE | ft.TextDecoration.LINE_THROUGH
        elif underscore:
            decoration = ft.TextDecoration.UNDERLINE
        elif strikethrough:
            decoration = ft.TextDecoration.LINE_THROUGH
        style = ft.TextStyle(
            font_family=self._font_family,
            size=self._font_size,
            height=MONO_LINE_HEIGHT,
            color=fg,
            bgcolor=None if bg == DEFAULT_BG else bg,
            italic=italics,
            decoration=decoration,
        )
        if len(self._styles) >= STYLE_CACHE_LIMIT:
            self._styles.clear()
        self._styles[spec] = style
        return style

    # --- Скрытое поле ввода ---

    def _on_field_change(self, event: ft.ControlEvent) -> None:
        """Значение поля -> байты PTY; поле всегда возвращается к пустому."""
        value = getattr(event, "data", None)
        if not isinstance(value, str):
            value = getattr(getattr(event, "control", None), "value", None)
        if not isinstance(value, str) and self._input is not None:
            value = self._input.value
        data = self._input_bridge.feed(value or "")
        self.clear_input()
        if data:
            self._on_bytes(data)

    def _on_field_submit(self, event: ft.ControlEvent) -> None:
        """Enter в поле ввода -> CR (само поле значение не меняет)."""
        self.clear_input()
        self._on_bytes(b"\r")

    def _on_field_focus(self, event: ft.ControlEvent) -> None:
        """Помечает, что печатаемые символы приходят из поля (IME)."""
        self._input_focused = True

    def _on_field_blur(self, event: ft.ControlEvent) -> None:
        """Фокус ушёл: печатаемые клавиши снова обрабатывает диспетчер."""
        self._input_focused = False

    def _on_click(self, event: ft.ControlEvent) -> None:
        """Клик по терминалу возвращает фокус скрытому полю ввода."""
        if self._on_focus_request is not None:
            self._on_focus_request()

    def clear_input(self) -> None:
        """Очищает поле ввода, чтобы оно отдавало по одному вводу за раз."""
        self._input_bridge.reset()
        if self._input is None:
            return
        self._input.value = ""
        try:
            self._input.update()
        except RuntimeError:
            pass  # Контрол ещё не примонтирован к странице.

    async def focus_input(self) -> None:
        """Просит фокус для поля ввода (иначе IME-символы не придут)."""
        if self._input is None:
            return
        try:
            await self._input.focus()
        except RuntimeError:
            return  # Контрол ещё не примонтирован к странице.
        self._input_focused = True

    # --- Размер ---

    def grid_size(self, width: float, height: float) -> tuple[int, int]:
        """Размер сетки в символах для пиксельного размера контейнера.

        Единственный источник правды о том, сколько символов влезает:
        тем же расчётом пользуется и пересчёт по размеру окна (см.
        `TerminalSession.resize_to_area`), иначе два пути давали бы разную
        сетку на одном и том же размере.

        Высота строки задана через `TextStyle.height` и точна (Flutter берёт
        ровно `height * fontSize`), а вот ширина знакоместа — доля кегля
        (`MONO_ASPECT`), то есть оценка. Поэтому в колонках держится запас в
        одно знакоместо: при промахе метрики справа останется пустая полоса,
        а не обрезанное `HARD_EDGE` приглашение. Дополнительно уменьшать
        число строк незачем — они уже гарантированно совпадают с контейнером.
        """
        if width <= 0 or height <= 0:
            return self._min_columns, self._min_lines
        width_budget = max(width - 2 * self._padding, 0.0)
        height_budget = max(height - 2 * self._padding, 0.0)
        columns = max(
            self._min_columns,
            int(width_budget // self._char_width) - GRID_COLUMN_SLACK,
        )
        lines = max(
            self._min_lines,
            int(height_budget // self._line_height),
        )
        return columns, lines

    def _on_size_change(self, event: ft.ControlEvent) -> None:
        """Сообщает наружу размер терминала в символах по пикселям контейнера."""
        if self._on_resize is None:
            return
        width = float(getattr(event, "width", 0) or 0)
        height = float(getattr(event, "height", 0) or 0)
        if width <= 0 or height <= 0:
            # Контейнер ещё не разложен: `min_columns x min_lines` схлопнули бы
            # окно PTY и заставили шелл перерисовать подсказку в 4 строки.
            return
        size = self.grid_size(width, height)
        if size == self._size:
            return
        self._size = size
        self._on_resize(*size)
