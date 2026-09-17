# termoclub/core/sessions/terminal/SmartCLIScreen_test.py
"""Тесты экрана-адаптера smartcli (ScreenModel -> интерфейс TerminalView)."""
from __future__ import annotations

from smartcli_core import CellAttrs, ScreenModel

from core.sessions.terminal.SmartCLIScreen import SmartCLIScreen


def _screen(text: str = "", columns: int = 20, lines: int = 4) -> SmartCLIScreen:
    model = ScreenModel(columns, lines)
    if text:
        model.feed(text.encode("utf-8"))
    return SmartCLIScreen(model)


def test_geometry_matches_the_model() -> None:
    """Размер берётся из модели, а не из аргументов конструктора."""
    screen = _screen(columns=30, lines=7)
    assert (screen.columns, screen.lines) == (30, 7)


def test_cursor_is_reported_as_x_y() -> None:
    """ScreenModel отдаёт (row, column), а TerminalView ждёт (x, y)."""
    screen = _screen("ab", columns=10, lines=3)
    assert screen.cursor == (2, 0)


def test_hidden_cursor_is_none() -> None:
    """DECTCEM выключен — курсора нет (как у PyteScreen, иначе рисовался бы)."""
    screen = _screen("ab\x1b[?25l", columns=10, lines=3)
    assert screen.cursor is None


def test_row_returns_pyte_cells_with_full_attributes() -> None:
    """row(y) отдаёт ячейки pyte целиком: TerminalView рисует начертания."""
    screen = _screen("\x1b[1;4mX", columns=5, lines=2)
    cells = screen.row(0)
    assert len(cells) == 5
    assert cells[0].data == "X"
    assert cells[0].bold is True
    assert cells[0].underscore is True
    assert cells[1].data == " "


class _ModelWithoutScreen:
    """Модель без публичного `screen` — эмуляция рефакторинга smartcli."""

    cols = 5
    rows = 2
    display = ["X    ", "     "]

    def row_cells(self, row: int) -> list[CellAttrs]:
        """Урезанные ячейки: начертаний в `CellAttrs` нет вовсе."""
        first = CellAttrs("X", "default", "default", True, False)
        return [first] + [CellAttrs(" ", "default", "default", False, False)] * 4


def test_row_falls_back_when_the_model_hides_its_screen() -> None:
    """`screen` — деталь реализации smartcli: адаптер деградирует, а не падает."""
    screen = SmartCLIScreen(_ModelWithoutScreen())  # type: ignore[arg-type]

    assert (screen.columns, screen.lines) == (5, 2)
    cells = screen.row(0)
    assert len(cells) == 5
    assert cells[0].data == "X"
    assert cells[0].bold is True
    assert cells[0].underscore is False  # на запасном пути начертания теряются


def test_feed_bytes_is_a_no_op() -> None:
    """Чанк уже скармливает PtySession.pump(): повторное кормление недопустимо."""
    screen = _screen(columns=10, lines=2)
    screen.feed_bytes(b"hello")
    assert screen.text().strip() == ""


def test_resize_reports_whether_it_changed() -> None:
    """resize() возвращает True только на реальном изменении (как PyteScreen)."""
    screen = _screen(columns=20, lines=4)
    assert screen.resize(30, 6) is True
    assert (screen.columns, screen.lines) == (30, 6)
    assert screen.resize(30, 6) is False


def test_visible_text_drops_padding_and_empty_lines() -> None:
    """Копируется только осмысленный текст: без правых пробелов и хвоста."""
    screen = _screen("one\r\ntwo", columns=12, lines=5)
    assert screen.visible_text() == "one\ntwo"


def test_utf8_split_across_feeds_is_reassembled() -> None:
    """Кириллица, разрезанная чанком, не превращается в «ромбики»."""
    model = ScreenModel(10, 2)
    encoded = "привет".encode("utf-8")
    model.feed(encoded[:5])
    model.feed(encoded[5:])
    assert "привет" in SmartCLIScreen(model).text()
