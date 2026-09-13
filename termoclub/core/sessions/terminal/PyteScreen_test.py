# termoclub/core/sessions/terminal/PyteScreen_test.py
"""Тесты экрана pyte: эмуляция, атрибуты, UTF-8, размер, курсор."""
from __future__ import annotations

from core.sessions.terminal.PyteScreen import PyteScreen


def test_text_and_initial_size() -> None:
    """Новый экран пуст и имеет переданный размер."""
    screen = PyteScreen(columns=10, lines=3)
    assert (screen.columns, screen.lines) == (10, 3)
    assert screen.text().splitlines()[0] == " " * 10


def test_escape_sequences_are_emulated() -> None:
    """ANSI-последовательности применяются (в text() видны без escape)."""
    screen = PyteScreen(columns=20, lines=2)
    screen.feed("\x1b[31mred\x1b[0m normal\r\n")
    assert "red normal" in screen.text()
    assert "\x1b" not in screen.text()


def test_attributes_are_kept_per_cell() -> None:
    """Цвет и атрибуты доступны через row()."""
    screen = PyteScreen(columns=10, lines=1)
    screen.feed("\x1b[1;31mR")
    first = screen.row(0)[0]
    assert first.data == "R"
    assert first.fg == "red"
    assert first.bold is True
    assert screen.row(0)[1].fg == "default"


def test_cursor_position_and_visibility() -> None:
    """Курсор отдаётся с позицией и прячется по DECTCEM."""
    screen = PyteScreen(columns=10, lines=3)
    screen.feed("ab")
    assert screen.cursor == (2, 0)
    screen.feed("\x1b[?25l")
    assert screen.cursor is None


def test_utf8_survives_chunk_boundaries() -> None:
    """Многобайтовый символ, разрезанный чанком, не ломается."""
    screen = PyteScreen(columns=10, lines=1)
    chunk = "ф".encode("utf-8")
    screen.feed_bytes(chunk[:1])
    screen.feed_bytes(chunk[1:])
    assert screen.text().startswith("ф")


def test_visible_text_trims_padding_and_empty_tail() -> None:
    """Для буфера обмена пустые поля срезаются, пустой хвост отбрасывается."""
    screen = PyteScreen(columns=12, lines=4)
    screen.feed("one\r\ntwo")
    assert screen.visible_text() == "one\ntwo"
    assert PyteScreen(columns=8, lines=3).visible_text() == ""


def test_resize_reports_change() -> None:
    """resize() меняет размер и сообщает, изменился ли он."""
    screen = PyteScreen(columns=80, lines=24)
    assert screen.resize(80, 24) is False
    assert screen.resize(100, 30) is True
    assert (screen.columns, screen.lines) == (100, 30)
    assert len(screen.row(29)) == 100
