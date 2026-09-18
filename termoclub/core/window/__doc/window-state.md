# Main window state

TermoClub remembers how the main window looked when the user last used it.
This document describes what is stored, where it lives, and how the pieces
fit together.

## What is remembered

A single snapshot, `WindowState`:

| Field              | Meaning                                             |
| ------------------ | --------------------------------------------------- |
| `width`, `height`  | Window size in pixels.                              |
| `maximized`        | Whether the window was maximized.                   |
| `left_panel_open`  | Whether the left slide-out panel was expanded.      |
| `right_panel_open` | Whether the right slide-out panel was expanded.     |
| `tabs`             | Reserved. See "Open tabs" below.                    |

The reserved `tabs` field is serialized and survives a round trip, but nothing
writes to it yet. Restoring open tabs is a separate task; keeping the field in
the schema now means the file format will not have to change when it lands.

## Where it lives

`~/.termoclub/window/state.json`, under the user profile and next to the other
user data. It is deliberately not part of `~/.termoclub/settings`: settings are
portable preferences, while the window state describes one machine's display.

## Layers

Two classes, each in its own file:

- `core/window/WindowState.py` — the snapshot itself, plus tolerant parsing.
  Every field is repaired independently, so one bad value does not discard the
  rest of the file. Sizes below `MIN_WIDTH`/`MIN_HEIGHT` and non-numeric values
  fall back to defaults; `true` is rejected as a size even though
  `isinstance(True, int)` holds.
- `core/window/WindowStateStore.py` — the mediator between the JSON file and
  the UI. It reads through `FileManager`, writes back on change, and falls back
  to defaults when the profile is missing or the file is corrupt.

The UI never touches the state file. `main.py` asks the store, never the
filesystem.

## Defaults and priority

When no file exists yet the defaults apply: 1200x800, not maximized, both side
panels collapsed. A saved snapshot takes priority over those defaults, field by
field. If the profile is unavailable, the store switches to read-only: the app
still starts with defaults and `save()` returns `False` instead of raising.

## When the state is written

**Once, when the window closes.** Everything the user does in the meantime —
moving an edge, opening a panel — only updates the in-memory snapshot. The
disk is touched on the single save, deliberately: writing the view state on
every interaction would put needless wear on an SSD, and nothing is lost if
the process dies first. A crash means the next launch starts clean, which is
an accepted outcome for view state.

The writers, all funnelling into `_save_window_state`:

- `page.on_close` and `page.on_disconnect` — the normal close path.
- the Exit menu item — the same save, for the case where focus is in the menu.
- `on_resize` **does not** save; it calls `_remember_window_size`, which only
  updates memory (and skips the update when the size is unchanged).
- `on_panel_toggle` does not save either: `update(save=False)` by default.

`WindowStateStore.update` therefore defaults to `save=False`, so the safe path
is the one taken by accident. `save=True` exists for the rare caller that needs
an immediate write, and `save()` is public for the explicit case.

Programmatic restoration uses `ApplicationLayout.set_panel_visible`, which does
not fire the toggle callback. Otherwise restoring a snapshot would try to write
back what was just read.

If the process is killed before the close handler runs, the file keeps its
previous contents and the next launch starts from that — or from defaults if
there was never a save.

## Startup flow

`TermoClubApp.__init__` reads the store before building the layout, and
`_panel_config` turns the saved flags into `PanelConfig`. Panels therefore
render in their saved visibility on the first frame instead of animating from
the default. `start()` then applies the saved window size to `page.window`.

In web mode the browser dictates the window size and may ignore the value
written to `page.window`; the app accepts that and still records the state.

## Startup tabs

No tab is opened on launch by default. The `startup_session` setting in the
global category controls this and now defaults to `none`; picking `terminal` or
`terminal-gpu` restores the old behaviour. See `__doc/workspace-tabs.md` for the
workspace itself.

## Deep links

`start()` renders the route it gets from `page.route`, so opening the app at
`/settings` or `/logs` goes straight to that section. Only the known routes are
honoured; anything else falls back to `/` rather than leaving the workspace
empty.

`page.route` is populated by the client when the session is created, so this is
available on the very first frame without waiting for `on_route_change`, which
does not fire for the initial route.
