# termoclub/app/ui/SystemStatuses_test.py
"""Tests for the SystemStatuses class."""
from __future__ import annotations

import flet as ft

from app.ui.SystemStatuses import SystemStatuses


def test_build_returns_three_indicators() -> None:
    """The panel renders three status indicators."""
    panel = SystemStatuses().build()
    assert isinstance(panel, ft.Row)
    assert isinstance(panel.controls, list)
    assert len(panel.controls) == 3


def test_set_status_changes_indicator_color() -> None:
    """set_status recolors a known indicator without a mounted page."""
    statuses = SystemStatuses()
    statuses.build()
    statuses.set_status("link", ft.Colors.RED)
    assert statuses._indicators["link"].color == ft.Colors.RED


def test_set_status_unknown_name_is_ignored() -> None:
    """set_status with an unknown name does nothing and does not raise."""
    statuses = SystemStatuses()
    statuses.build()
    statuses.set_status("no-such-process", ft.Colors.RED)
