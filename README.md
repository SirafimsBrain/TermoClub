# TermoClub

A pet Python **Flet** project: a small desktop app that controls terminal emulators through a standardized interface.

The default terminal implementation is **Ghostty**, with an isolation layer that makes it easy to add others (Kitty and beyond) later.

## Architecture

The app is split into three layers:

1. **UI layer (Flet)** — rendering and user actions only. Uses routes (`/`, `/logs`). Knows nothing about a concrete terminal; works exclusively through the standardized `TerminalController` interface.
2. **Standardized layer** — the abstract `TerminalController` (ABC) with a unified contract and a single `Result` format (`ok` + `message`):
   - `open_new_window(command=None, cwd=None) -> Result`
   - `open_new_tab(command=None, cwd=None) -> Result` (mandatory part of the contract)
   - `focus() -> Result`
3. **Terminal isolation layer** — each terminal implementation lives in its own package (`ghostty/`, `kitty/`). Ghostty has its own platform abstraction inside (macOS via AppleScript, Linux via CLI). The factory creates the right controller by name from the config; new terminals = implement the interface + register in the factory. The UI and the rest of the code stay unchanged.

Supporting pieces:

- `config.py` — which terminal is active by default (`ghostty`), overridable via the `TERMOCLUB_TERMINAL` env var.
- `logging_setup.py` — centralized logger: file (`logs/termoclub.log`, rotating) + console.
- `events.py` — extension point for terminal events (tab colors, etc.), currently a stub.

## Project structure

```
ghostty_wrapper/
├── main.py                         # Entry point, starts Flet
├── app/
│   ├── routes.py                   # Routes and navigation
│   ├── pages/
│   │   ├── home.py                 # Main screen
│   │   └── logs.py                 # Logs screen (stub)
│   ├── ui/
│   │   └── components.py           # Reusable UI elements
│   └── state.py                    # Minimal app state
├── core/
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
│   └── result.py                   # Unified Result format
├── logging_setup.py
└── logs/
```

## Requirements

- Python 3.13+
- [Flet](https://flet.dev) — `pip install flet`
- [Ghostty](https://ghostty.org) installed and on `PATH` (Linux: `+new-window` CLI; macOS: AppleScript dictionary)

## Installation and run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python ghostty_wrapper/main.py
```

To switch the active terminal (must be supported by the factory):

```bash
TERMOCLUB_TERMINAL=ghostty python ghostty_wrapper/main.py
```

## Tests

```bash
python -m pytest -q
```

## Roadmap

- Implement Kitty via its remote-control protocol (`kitty @ new-window` / `new-tab`).
- Tab colors and other terminal events through `events.py`.

## License

See [LICENSE](LICENSE).