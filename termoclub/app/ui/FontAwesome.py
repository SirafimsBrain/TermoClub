# termoclub/app/ui/FontAwesome.py
"""Local Font Awesome Free icons for the Flet UI.

Flet's `ft.Icon` renders Material icons only, so Font Awesome glyphs
are rendered with `ft.Text` using the bundled OTF files (see
`termoclub/assets/fonts/`). Use `FontAwesome.icon()` to get one.
"""
from __future__ import annotations

import flet as ft

#: Asset paths (relative to Flet `assets_dir`) of the bundled fonts.
FONTS: dict[str, str] = {
    "FA Solid": "/fonts/fa-solid-900.otf",
    "FA Regular": "/fonts/fa-regular-400.otf",
    "FA Brands": "/fonts/fa-brands-400.otf",
    # Monospace for the internal terminal (JetBrains Mono, SIL OFL 1.1).
    "JetBrains Mono": "/fonts/jb-mono-regular.ttf",
}

#: Curated subset of icons: name -> (unicode codepoint, font family).
#: Codepoints come from the desktop bundle metadata (`icons.json`).
_ICONS: dict[str, tuple[int, str]] = {
    "terminal": (0xF120, "FA Solid"),
    "house": (0xF015, "FA Solid"),
    "plus": (0x002B, "FA Solid"),
    "chevron-left": (0xF053, "FA Solid"),
    "chevron-right": (0xF054, "FA Solid"),
    "open-in-new": (0xF08E, "FA Solid"),
    "newspaper": (0xF1EA, "FA Solid"),
    "gear": (0xF013, "FA Solid"),
    "folder": (0xF07B, "FA Solid"),
    "puzzle-piece": (0xF12E, "FA Solid"),
    "file-lines": (0xF15C, "FA Solid"),
    "circle-info": (0xF05A, "FA Solid"),
    "xmark": (0xF00D, "FA Solid"),
    "bars": (0xF0C9, "FA Solid"),
    "search": (0xF002, "FA Solid"),
    "history": (0xF1DA, "FA Solid"),
    "wifi": (0xF1EB, "FA Solid"),
    "bell": (0xF0F3, "FA Solid"),
    "circle-check": (0xF058, "FA Solid"),
    "grip-vertical": (0xF58E, "FA Solid"),
    "window-maximize": (0xF2D0, "FA Solid"),
    # Категории настроек: иконка задаётся схемой, поэтому набор шире
    # базового интерфейса.
    "globe": (0xF0AC, "FA Solid"),
    "palette": (0xF53F, "FA Solid"),
    "bolt": (0xF0E7, "FA Solid"),
    "wrench": (0xF0AD, "FA Solid"),
    "sliders": (0xF1DE, "FA Solid"),
    "font": (0xF031, "FA Solid"),
    "sun": (0xF185, "FA Solid"),
    "moon": (0xF186, "FA Solid"),
    "link": (0xF0C1, "FA Solid"),
    "calendar": (0xF133, "FA Solid"),
    "image": (0xF03E, "FA Solid"),
    "clock-rotate-left": (0xF1DA, "FA Solid"),
    "flask": (0xF0C3, "FA Solid"),
    "plug": (0xF1E6, "FA Solid"),
    "star": (0xF005, "FA Solid"),
    "folder-open": (0xF07C, "FA Solid"),
    "wand-magic-sparkles": (0xE2CA, "FA Solid"),
}


class FontAwesome:
    """Helper for Font Awesome Free icons bundled with the app."""

    @staticmethod
    def register(page: ft.Page) -> None:
        """Registers the bundled fonts on the page (call once at startup)."""
        fonts = dict(page.fonts or {})
        fonts.update(FONTS)
        page.fonts = fonts

    @staticmethod
    def icon(name: str, size: int = 16, color: str | None = None) -> ft.Text:
        """Returns a Text control rendering the named icon glyph."""
        try:
            codepoint, family = _ICONS[name]
        except KeyError:
            raise ValueError(f"Unknown Font Awesome icon: {name!r}") from None
        return ft.Text(chr(codepoint), font_family=family, size=size, color=color)
