# termoclub/app/ui/FontAwesome_test.py
"""Tests for the FontAwesome helper."""
from __future__ import annotations

from pathlib import Path

import flet as ft
import pytest

from app.ui.FontAwesome import FONTS, FontAwesome


class _FakePage:
    def __init__(self) -> None:
        self.fonts: dict | None = None


def test_register_adds_bundled_fonts() -> None:
    """register() exposes all bundled families on the page."""
    page = _FakePage()
    FontAwesome.register(page)  # type: ignore[arg-type]
    assert page.fonts == FONTS


def test_register_keeps_existing_fonts() -> None:
    """register() does not drop fonts registered earlier."""
    page = _FakePage()
    page.fonts = {"Other": "/fonts/other.ttf"}
    FontAwesome.register(page)  # type: ignore[arg-type]
    assert page.fonts is not None
    assert page.fonts["Other"] == "/fonts/other.ttf"
    assert page.fonts["FA Solid"] == "/fonts/fa-solid-900.otf"


def test_icon_returns_text_with_glyph_and_family() -> None:
    """icon() returns a Text with the PUA glyph and the right family."""
    control = FontAwesome.icon("terminal", size=18)
    assert isinstance(control, ft.Text)
    assert control.value == chr(0xF120)
    assert control.font_family == "FA Solid"
    assert control.size == 18


def test_icon_unknown_name_raises() -> None:
    """icon() raises ValueError for names outside the curated subset."""
    with pytest.raises(ValueError):
        FontAwesome.icon("no-such-icon")


def test_bundled_font_files_exist() -> None:
    """All OTF files referenced by FONTS exist under assets/fonts."""
    assets = Path(__file__).resolve().parent.parent.parent / "assets"
    for asset_path in FONTS.values():
        assert (assets / asset_path.lstrip("/")).exists()
