# termoclub/app/ui/MainMenu_test.py
"""Tests for the MainMenu class."""
from __future__ import annotations

import asyncio
import inspect

import flet as ft

from app.ui.MainMenu import MainMenu


def _texts(control: ft.Control) -> list[str]:
    """Collects all Text values in a MenuBar tree."""
    found: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, ft.Text) and isinstance(node.value, str):
            found.append(node.value)
        controls = getattr(node, "controls", None)
        if isinstance(controls, list):
            for child in controls:
                visit(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            visit(content)

    visit(control)
    return found


def _click_by_label(menu_bar: ft.MenuBar, label: str) -> None:
    """Finds a MenuItemButton by label and invokes its on_click."""
    clicked: list[bool] = []

    def visit(node: object) -> None:
        if isinstance(node, ft.MenuItemButton):
            content = node.content
            if isinstance(content, ft.Text) and content.value == label:
                assert node.on_click is not None
                result = node.on_click(None)  # type: ignore[arg-type]
                if inspect.isawaitable(result):
                    asyncio.run(result)
                clicked.append(True)
        for attr in ("controls",):
            children = getattr(node, attr, None)
            if isinstance(children, list):
                for child in children:
                    visit(child)
        content_attr = getattr(node, "content", None)
        if isinstance(content_attr, ft.Control):
            visit(content_attr)

    visit(menu_bar)
    assert clicked, f"menu item {label!r} not found"


def test_build_has_three_top_level_menus() -> None:
    """MenuBar contains Home, Settings and Help submenus."""
    bar = MainMenu().build()
    assert isinstance(bar, ft.MenuBar)
    assert isinstance(bar.controls, list)
    assert len(bar.controls) == 3
    labels = _texts(bar)
    assert "Home" in labels
    assert "Settings" in labels
    assert "Help" in labels


def test_exit_item_triggers_on_exit() -> None:
    """The mandatory Exit item calls the on_exit callback."""
    calls: list[bool] = []
    bar = MainMenu(on_exit=lambda: calls.append(True)).build()
    assert isinstance(bar, ft.MenuBar)
    _click_by_label(bar, "Exit")
    assert calls == [True]


def test_dashboard_triggers_navigation() -> None:
    """Dashboard navigates home, Event Log navigates to logs."""
    routes: list[str] = []
    bar = MainMenu(on_navigate=routes.append).build()
    assert isinstance(bar, ft.MenuBar)
    _click_by_label(bar, "Dashboard")
    _click_by_label(bar, "Event Log")
    assert routes == ["/", "/logs"]


def test_settings_has_nested_preferences_submenu() -> None:
    """Settings demonstrates nesting via the Preferences submenu."""
    bar = MainMenu().build()
    assert isinstance(bar, ft.MenuBar)
    assert "Preferences" in _texts(bar)
    assert "Appearance" in _texts(bar)
    assert "Terminal" in _texts(bar)


def test_internal_terminal_triggers_callback() -> None:
    """Internal Terminal opens a workspace session via callback."""
    calls: list[bool] = []
    bar = MainMenu(on_new_session=lambda: calls.append(True)).build()
    assert isinstance(bar, ft.MenuBar)
    _click_by_label(bar, "Internal Terminal")
    assert calls == [True]
