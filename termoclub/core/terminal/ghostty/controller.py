# termoclub/core/terminal/ghostty/controller.py
"""Высокоуровневая обёртка над управлением терминалом Ghostty."""
from __future__ import annotations

import sys

from core.result import Result
from core.terminal.base import TerminalController
from core.terminal.ghostty.platform.base import GhosttyPlatform
from core.terminal.ghostty.platform.linux import GhosttyLinux
from core.terminal.ghostty.platform.macos import GhosttyMacOS


def _build_platform() -> GhosttyPlatform:
    """Создаёт платформенную реализацию Ghostty."""
    if sys.platform == "darwin":
        return GhosttyMacOS()
    return GhosttyLinux()


class GhosttyController(TerminalController):
    """Контроллер Ghostty: делегирует вызовы платформенному уровню."""

    def __init__(self, platform: GhosttyPlatform | None = None) -> None:
        self._platform = platform or _build_platform()

    def open_new_window(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        return self._platform.open_new_window(command=command, cwd=cwd)

    def open_new_tab(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        return self._platform.open_new_tab(command=command, cwd=cwd)

    def focus(self) -> Result:
        return self._platform.focus()