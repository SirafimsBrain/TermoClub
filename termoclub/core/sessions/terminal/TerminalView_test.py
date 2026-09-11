# termoclub/core/sessions/terminal/TerminalView_test.py
"""Тесты Flet-стороны терминала (без GUI): спаны, ввод, размер."""
from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from core.sessions.terminal.PyteScreen import PyteScreen
from core.sessions.terminal.TerminalPalette import DEFAULT_BG, DEFAULT_FG
from core.sessions.terminal.TerminalView import TerminalView


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
    # padding 8 -> (600-16)/6 = 97 колонок, (200-16)/12.5 = 14 строк.
    assert resized == [(97, 14)]
    view._on_size_change(_size(600, 200))
    assert resized == [(97, 14)]  # повтор того же размера не рассылается


def test_tiny_size_falls_back_to_minimums() -> None:
    """Слишком маленький контейнер даёт минимальную сетку."""
    resized: list[tuple[int, int]] = []
    view, _ = _view(on_resize=lambda c, l: resized.append((c, l)))
    view.control
    view._on_size_change(_size(4, 4))
    assert resized == [(20, 4)]
