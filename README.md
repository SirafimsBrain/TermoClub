# TermoClub

A pet Python **Flet** project: a small desktop app that controls terminal emulators through a standardized interface.

The default terminal implementation is **Ghostty**, with an isolation layer that makes it easy to add others (Kitty and beyond) later.

## Architecture

The app is split into three layers:

1. **UI layer (Flet)** — rendering and user actions only. The main window is a persistent 5-panel shell (top bar, collapsible left panel, central workspace, collapsible right panel, bottom status bar) ported from the Rhizome client layout. The top bar holds the main menu (`Home | Settings | Help`, with an `Exit` item), an expander, and system status icons; routes (`/`, `/logs`) swap only the workspace content. Knows nothing about a concrete terminal; works exclusively through the standardized `TerminalController` interface.
2. **Standardized layer** — the abstract `TerminalController` (ABC) with a unified contract and a single `Result` format (`ok` + `message`):
   - `open_new_window(command=None, cwd=None) -> Result`
   - `open_new_tab(command=None, cwd=None) -> Result` (mandatory part of the contract)
   - `focus() -> Result`
3. **Terminal isolation layer** — each terminal implementation lives in its own package (`ghostty/`, `kitty/`). Ghostty has its own platform abstraction inside (macOS via AppleScript, Linux via CLI). The factory creates the right controller by name from the config; new terminals = implement the interface + register in the factory. The UI and the rest of the code stay unchanged.

Supporting pieces:

- `config.py` — which terminal is active by default (`ghostty`), overridable via the `TERMOCLUB_TERMINAL` env var.
- `storage/` — user data (`~/.termoclub`) behind a single `FileManager` wrapper; archive and remote operations are stubs for now.
- `logging_setup.py` — centralized logger: file (`logs/termoclub.log`, rotating) + console.
- `events.py` — extension point for terminal events (tab colors, etc.), currently a stub.
- Icons — Font Awesome Free 7.3.1 (SIL OFL 1.1), bundled locally under `termoclub/assets/fonts/` and rendered via `ft.Text` through the `FontAwesome` helper (Flet `ft.Icon` stays Material-only).

## Project structure

```
termoclub/
├── main.py                         # Entry point + 5-panel shell (top/left/workspace/right/bottom)
├── app/
│   ├── routes.py                   # Routes and navigation
│   ├── layout.py                   # CollapsiblePanel + ApplicationLayout (ported from Rhizome client)
│   ├── pages/
│   │   ├── home.py                 # Main screen content (workspace)
│   │   └── logs.py                 # Logs screen content (workspace)
│   ├── ui/
│   │   ├── components.py           # Reusable UI elements
│   │   ├── WorkspaceTabBar.py      # Custom tab bar (Row, no ft.Tabs)
│   │   ├── WorkspaceStage.py       # Tab content host (ft.Stack)
│   │   ├── SessionCard*.py         # Session cards for the left panel
│   ├── workspace/
│   │   └── WorkspaceManager.py     # Tab/session state (no Flet state)
│   └── state.py                    # Minimal app state
├── core/
│   ├── sessions/                   # WorkspaceItem ABC, SessionFactory, terminal/editor/rdp
│   │                               # (both terminals are pure Python: `terminal` renders
│   │                               # via pyte + Flet, `terminal-gpu` via smartcli-toolkit)
│   ├── terminal/
│   │   ├── base.py                 # Abstract TerminalController
│   │   ├── factory.py              # Factory / registry
│   │   ├── ghostty/
│   │   │   ├── controller.py       # High-level Ghostty wrapper
│   │   │   └── platform/
│   │   │       ├── base.py
│   │   │       ├── macos.py        # AppleScript
│   │   │       └── linux.py        # CLI (+new-window)
│   │   └── kitty/                  # Kitty stub
│   ├── events.py                   # Terminal events (stub)
│   ├── config.py                   # Active terminal + settings
│   ├── storage/                    # User data: FileManager + backends (profile `~/.termoclub`)
│   └── result.py                   # Unified Result format
├── logging_setup.py
└── logs/
```

## Requirements

- Python 3.13+
- Dependencies from `requirements.txt`: [Flet](https://flet.dev) (verified on `1.0.0`; the file itself stays unpinned), [`smartcli-toolkit`](https://pypi.org/project/smartcli-toolkit/) (verified on `0.3.2`; PTY and screen model for the `Terminal (smartcli)` tab) and `pyte` (`0.8.2`, screen emulation for the `Terminal (pyte)` tab)
- [Ghostty](https://ghostty.org) installed and on `PATH` for the **external** terminal (menu items New Tab / New Window; Linux: `+new-window` CLI; macOS: AppleScript dictionary)

## Built-in terminal: input and size

- **Text input** goes through the hidden IME field of the tab (`TerminalView`), so Cyrillic, case and paste follow the OS layout. Service keys and `Ctrl+<letter>` come from `page.on_keyboard_event`, where Flet exposes only logical (US) key labels.
- **Clipboard**: `Ctrl+Shift+V` / `Ctrl+Insert` copy the visible screen, `Ctrl+V` / `Shift+Insert` paste; plain `Ctrl+C` stays SIGINT for the shell.
- **Cursor keys** switch to the SS3 form (`ESC O A`) while a program enables DECCKM (`smkx`), the way `mc`, `vim`, `htop` and `less` expect — the session reads that mode from the PTY output itself.
- **Size**: the tab container is the single source of truth (`TerminalView.measured`). The window-based estimate is only a fallback for a tab that has not been laid out yet, so the grid and the PTY never disagree.

## Installation and run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python termoclub/main.py
```

To switch the active terminal (must be supported by the factory):

```bash
TERMOCLUB_TERMINAL=ghostty python termoclub/main.py
```

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

## Roadmap

- Implement Kitty via its remote-control protocol (`kitty @ new-window` / `new-tab`).
- Tab colors and other terminal events through `events.py`.

## License

See [LICENSE](LICENSE).