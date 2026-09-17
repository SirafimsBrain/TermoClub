# termoclub/core/window/WindowState_test.py
"""Тесты снимка состояния окна: разбор полей и устойчивость к мусору."""
from __future__ import annotations

from core.window.WindowState import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    WindowState,
)


def test_defaults_have_panels_closed() -> None:
    """По умолчанию панели свёрнуты, а вкладки не восстанавливаются."""
    state = WindowState()
    assert (state.left_panel_open, state.right_panel_open) == (False, False)
    assert state.tabs == []
    assert (state.width, state.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def test_round_trip_through_dict() -> None:
    """Снимок переживает сериализацию без потерь."""
    original = WindowState(
        width=1440,
        height=900,
        maximized=True,
        left_panel_open=True,
        right_panel_open=False,
        tabs=[{"kind": "terminal", "title": "ops"}],
    )
    assert WindowState.from_dict(original.to_dict()) == original


def test_too_small_size_falls_back_to_default() -> None:
    """Размер меньше минимального заменяется умолчанием, а не 0."""
    state = WindowState.from_dict({"width": MIN_WIDTH - 1, "height": MIN_HEIGHT - 1})
    assert (state.width, state.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def test_minimum_size_is_accepted() -> None:
    """Граничный размер ещё считается пригодным."""
    state = WindowState.from_dict({"width": MIN_WIDTH, "height": MIN_HEIGHT})
    assert (state.width, state.height) == (MIN_WIDTH, MIN_HEIGHT)


def test_non_numeric_and_bool_sizes_fall_back() -> None:
    """Строка и булево в размере не превращаются в число.

    `isinstance(True, int)` истинно, поэтому `true` в `width` без отдельной
    проверки дало бы окно шириной 1 px.
    """
    state = WindowState.from_dict({"width": "wide", "height": True})
    assert (state.width, state.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def test_flags_accept_zero_and_one() -> None:
    """Флаги панелей принимаются и как булево, и как 0/1."""
    state = WindowState.from_dict({"left_panel_open": 1, "right_panel_open": 0})
    assert (state.left_panel_open, state.right_panel_open) == (True, False)


def test_broken_tabs_are_filtered() -> None:
    """В зарезервированном списке вкладок остаются только словари."""
    state = WindowState.from_dict({"tabs": ["junk", 5, {"kind": "terminal"}]})
    assert state.tabs == [{"kind": "terminal"}]


def test_non_dict_payload_gives_defaults() -> None:
    """Не словарь на входе не роняет разбор."""
    assert WindowState.from_dict("nonsense") == WindowState()
    assert WindowState.from_dict(None) == WindowState()