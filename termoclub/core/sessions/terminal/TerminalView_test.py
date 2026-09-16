# termoclub/core/sessions/terminal/TerminalView_test.py
"""Тесты Flet-стороны терминала (без GUI): спаны, ввод, размер."""
from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from core.sessions.terminal.PyteScreen import PyteScreen
from core.sessions.terminal.TerminalPalette import DEFAULT_BG, DEFAULT_FG
from core.sessions.terminal.TerminalView import MONO_LINE_HEIGHT, TerminalView


def _view(**kwargs) -> tuple[TerminalView, list[bytes]]:
    written: list[bytes] = []
    view = TerminalView(on_bytes=written.append, **kwargs)
    return view, written


def _change(value: str) -> SimpleNamespace:
    return SimpleNamespace(data=value, control=SimpleNamespace(value=""))


def _size(width: float, height: float) -> SimpleNamespace:
    return SimpleNamespace(width=width, height=height)


def _text(spans: list[ft.TextSpan]) -> str:
    return "".join(span.text or "" for span in spans)


def test_control_is_built_once_with_hidden_input() -> None:
    """Контрол строится один раз и содержит скрытое поле ввода."""
    view, _ = _view()
    control = view.control
    assert isinstance(control, ft.Control)
    assert view.control is control
    assert view.input_ready is True
    assert view._input.opacity == 0
    assert view._input.autofocus is True


def test_plain_screen_rendering() -> None:
    """Текст экрана и вертикальные переводы строк попадают в спаны."""
    view, _ = _view()
    view.control
    screen = PyteScreen(columns=10, lines=2)
    screen.feed("hi\r\nthere")
    rendered = _text(view.spans(screen))
    assert rendered.startswith("hi")
    assert "there" in rendered
    assert rendered.count("\n") == 1


def test_colors_and_bold_render_as_spans() -> None:
    """ANSI-цвета и жирный текст превращаются в стили спанов."""
    view, _ = _view()
    view.control
    screen = PyteScreen(columns=10, lines=1)
    screen.feed("\x1b[31mred")
    red = view.spans(screen)[0]
    assert red.text == "red"
    assert red.style.color == "#cd0000"
    screen2 = PyteScreen(columns=10, lines=1)
    screen2.feed("\x1b[1;32mgo")
    bold = view.spans(screen2)[0]
    assert bold.style.color == "#55ff55"


def test_background_color_is_emitted() -> None:
    """Цвет фона ячейки попадает в bgcolor; фон по умолчанию не дублируется."""
    view, _ = _view()
    view.control
    screen = PyteScreen(columns=6, lines=1)
    screen.feed("\x1b[44mX")
    span = next(s for s in view.spans(screen) if s.text == "X")
    assert span.style.bgcolor == "#0000ee"
    plain = PyteScreen(columns=6, lines=1)
    plain.feed("y")
    plain_span = next(s for s in view.spans(plain) if s.text == "y")
    assert plain_span.style.bgcolor is None


def test_cursor_is_drawn_and_clamped() -> None:
    """Курсор рисуется инвертированной ячейкой, пустой хвост не рисуется."""
    view, _ = _view()
    view.control
    screen = PyteScreen(columns=8, lines=1)
    screen.feed("ab")
    spans = view.spans(screen)
    assert _text(spans) == "ab "
    cursor = spans[-1]
    assert cursor.text == " "
    assert cursor.style.color == DEFAULT_BG
    assert cursor.style.bgcolor == DEFAULT_FG


def test_hidden_cursor_is_not_drawn() -> None:
    """При скрытом курсоре пустой хвост строки не отрисовывается."""
    view, _ = _view()
    view.control
    screen = PyteScreen(columns=8, lines=1)
    screen.feed("ab\x1b[?25l")
    assert _text(view.spans(screen)) == "ab"


def test_field_change_sends_bytes_and_clears_input() -> None:
    """Значение скрытого поля уходит в PTY как UTF-8, поле очищается."""
    view, written = _view()
    view.control
    view._on_field_change(_change("Привет"))
    assert written == ["Привет".encode("utf-8")]
    assert view._input.value == ""


def test_field_submit_sends_carriage_return() -> None:
    """Enter в поле ввода отправляет CR."""
    view, written = _view()
    view.control
    view._on_field_submit(_change(""))
    assert written == [b"\r"]


def test_size_change_reports_symbol_grid() -> None:
    """Размер контейнера переводится в колонки и строки."""
    resized: list[tuple[int, int]] = []
    view, _ = _view(on_resize=lambda c, l: resized.append((c, l)), font_size=10)
    view.control
    view._on_size_change(_size(600, 200))
    # padding 8 -> (600-16)/6 = 97 колонок минус запас на метрику, (200-16)/12.5 = 14 строк.
    assert resized == [(96, 14)]
    view._on_size_change(_size(600, 200))
    assert resized == [(96, 14)]  # повтор того же размера не рассылается


def test_tiny_size_falls_back_to_minimums() -> None:
    """Слишком маленький контейнер даёт минимальную сетку."""
    resized: list[tuple[int, int]] = []
    view, _ = _view(on_resize=lambda c, l: resized.append((c, l)))
    view.control
    view._on_size_change(_size(4, 4))
    assert resized == [(20, 4)]


def test_zero_size_is_ignored() -> None:
    """Неразложенный контейнер (0x0) не схлопывает окно PTY до минимума."""
    resized: list[tuple[int, int]] = []
    view, _ = _view(on_resize=lambda c, l: resized.append((c, l)))
    view.control
    view._on_size_change(_size(0, 0))
    view._on_size_change(_size(600, 0))
    assert resized == []
    view._on_size_change(_size(600, 200))
    assert len(resized) == 1


def test_terminal_is_a_clipped_grid_without_scrollbar() -> None:
    """Терминал — фиксированная сетка: скроллить нечего и негде.

    `ListView(auto_scroll=True)` раньше «прилипал» к низу, когда сетка не
    влезала во вьюпорт, и экран показывал только пустые строки вместо
    приглашения.
    """
    view, _ = _view()
    control = view.control
    assert control.clip_behavior == ft.ClipBehavior.HARD_EDGE
    stack = control.content
    assert isinstance(stack, ft.Stack)
    assert not any(isinstance(child, ft.ListView) for child in stack.controls)


def test_every_span_carries_the_line_height() -> None:
    """Высота строки задана у всех спанов: высота отрисовки предсказуема."""
    view, _ = _view()
    view.control
    screen = PyteScreen(columns=8, lines=3)
    screen.feed("ab\r\ncd")
    spans = view.spans(screen)
    assert spans
    assert all(span.style.height == MONO_LINE_HEIGHT for span in spans)
    assert _text(spans).count("\n") == 2


def test_grid_fits_into_the_reported_container_size() -> None:
    """Сетка считается по пикселям контейнера и целиком в него влезает."""
    resized: list[tuple[int, int]] = []
    view, _ = _view(on_resize=lambda c, l: resized.append((c, l)), font_size=10)
    view.control
    view._on_size_change(_size(600, 200))
    columns, lines = resized[-1]
    assert columns * view._char_width <= 600 - 2 * view._padding
    assert lines * view._line_height <= 200 - 2 * view._padding


def test_grid_keeps_a_column_of_slack() -> None:
    """В колонках держится запас: лучше пустая полоса, чем обрезанное приглашение.

    Ширина знакоместа — оценка (0.6em), и при промахе лишняя колонка ушла бы
    под `HARD_EDGE`. Строки такой запас не нужны: их высота задана через
    `TextStyle.height` и точна.
    """
    view, _ = _view(font_size=10)
    view.control
    columns, lines = view.grid_size(600, 200)
    budget_width = 600 - 2 * view._padding
    budget_height = 200 - 2 * view._padding
    assert (columns + 1) * view._char_width <= budget_width
    assert lines * view._line_height <= budget_height


def test_grid_size_is_the_single_source_of_truth() -> None:
    """Пересчёт по окну и событие контейнера дают одинаковую сетку."""
    resized: list[tuple[int, int]] = []
    view, _ = _view(on_resize=lambda c, l: resized.append((c, l)), font_size=10)
    view.control
    view._on_size_change(_size(640, 320))
    assert resized == [view.grid_size(640, 320)]


def test_zero_size_grid_is_the_minimum() -> None:
    """Неразложенный контейнер даёт минимальную сетку, а не отрицательную."""
    view, _ = _view()
    view.control
    assert view.grid_size(0, 0) == (20, 4)


def test_focus_is_tracked_and_click_requests_it() -> None:
    """Фокус поля отслеживается, а клик по терминалу его возвращает."""
    requested: list[bool] = []
    view, _ = _view(on_focus_request=lambda: requested.append(True))
    view.control
    assert view.input_focused is False
    view._on_field_focus(None)  # type: ignore[arg-type]
    assert view.input_focused is True
    view._on_field_blur(None)  # type: ignore[arg-type]
    assert view.input_focused is False
    view._on_click(None)  # type: ignore[arg-type]
    assert requested == [True]
