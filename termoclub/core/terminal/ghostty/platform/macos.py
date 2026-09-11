# termoclub/core/terminal/ghostty/platform/macos.py
"""Управление Ghostty на macOS через AppleScript."""
from __future__ import annotations

import logging
import subprocess

from core.result import Result
from core.terminal.ghostty.platform.base import GhosttyPlatform

logger = logging.getLogger(__name__)

_ERR_PREFIX = "Ошибка AppleScript: "


def _as_string(value: str) -> str:
    """Экранирует строку для AppleScript-литерала (кавычки удваиваются)."""
    return f'"{str(value).replace(chr(34), chr(34) * 2)}"'


def _run_osascript(script: str) -> Result:
    """Выполняет osascript и возвращает единый Result."""
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.exception("osascript не выполнен: %s", exc)
        return Result.failure(f"{_ERR_PREFIX}{exc}")

    if proc.returncode == 0:
        return Result.success("Ghostty: окно/вкладка создана (macOS)")

    message = (proc.stderr or proc.stdout or "неизвестная ошибка").strip()
    logger.error("osascript завершился с ошибкой: %s", message)
    return Result.failure(f"{_ERR_PREFIX}{message}")


def _cfg_script(command: str | None, cwd: str | None) -> list[str]:
    """Возвращает строки настройки surface configuration Ghostty."""
    lines = ["set cfg to new surface configuration"]
    if cwd:
        lines.append(f"set initial working directory of cfg to {_as_string(cwd)}")
    if command:
        lines.append(f"set command of cfg to {_as_string(command)}")
    return lines


def _window_script(command: str | None, cwd: str | None) -> str:
    """Сборка AppleScript для нового окна."""
    return "\n".join(
        [
            'tell application "Ghostty"',
            *_cfg_script(command, cwd),
            "set win to new window with configuration cfg",
            "end tell",
        ]
    )


def _tab_script(command: str | None, cwd: str | None) -> str:
    """Сборка AppleScript для новой вкладки в переднем окне."""
    return "\n".join(
        [
            'tell application "Ghostty"',
            "set win to front window",
            *_cfg_script(command, cwd),
            "set t to new tab in win with configuration cfg",
            "end tell",
        ]
    )


class GhosttyMacOS(GhosttyPlatform):
    """Управление Ghostty на macOS."""

    def open_new_window(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        script = _window_script(command, cwd)
        logger.info("AppleScript: создание окна (command=%r, cwd=%r)", command, cwd)
        return _run_osascript(script)

    def open_new_tab(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        script = _tab_script(command, cwd)
        logger.info("AppleScript: создание вкладки (command=%r, cwd=%r)", command, cwd)
        return _run_osascript(script)

    def focus(self) -> Result:
        return _run_osascript('tell application "Ghostty" to activate')