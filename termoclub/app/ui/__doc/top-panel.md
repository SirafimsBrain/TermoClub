# Top Panel (head/top)

## Decision

The top panel is a `Row` of three sections, left to right:

1. `MainMenu` panel — a bare `ft.MenuBar` (`Home | Settings | Help`).
2. Expander — a plain `ft.Container(expand=True)` that pins its neighbors
   to the edges of the parent panel. It has no behavior today.
3. `SystemStatuses` panel — placeholder process-status icons (link, bell, health).

The bar height is `PanelConfig.top_height = 40`: the minimum that still fits
the menu text and status glyphs without clipping.

Wiring lives in `TermoClubApp._setup_panels` (`termoclub/main.py`); the panel
classes themselves stay page-free and terminal-free.

## MainMenu (`termoclub/app/ui/MainMenu.py`)

- Built on `ft.MenuBar` / `ft.SubmenuButton` / `ft.MenuItemButton`
  (Flet 0.86; `ft.Icon` is Material-only, so item glyphs come from
  `FontAwesome.icon(...)` via the `leading` slot).
- Structure (simplest viable variant, with a nesting example):
  - `Home`: Dashboard (`/`), Event Log (`/logs`), divider,
    New Tab, New Window, divider, **Exit** (mandatory).
  - `Settings`: nested `Preferences` submenu (Appearance, Terminal — stubs),
    divider, About Terminals.
  - `Help`: Documentation, About (stubs).
- All behavior is injected through callbacks
  (`on_navigate`, `on_new_tab`, `on_new_window`, `on_info`, `on_exit`)
  so the class knows nothing about routes, pages, or terminals.
- `Exit` calls `TermoClubApp.exit_app`, which closes the window via
  `page.window.close()`.

## SystemStatuses (`termoclub/app/ui/SystemStatuses.py`)

- Three Font Awesome indicators (`wifi`, `bell`, `circle-check`) with tooltips.
- `set_status(name, color)` recolors an indicator; safe to call before the
  control is mounted (the `update()` is skipped then). Future process
  statuses should reuse this method instead of adding new controls.
