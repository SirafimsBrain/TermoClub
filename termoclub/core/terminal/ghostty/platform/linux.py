# termoclub/core/terminal/ghostty/platform/linux.py
"""Управление Ghostty на Linux через CLI (+new-window, D-Bus?)."""
from __future__ import annotations

import logging
import shlex
import subprocess

from core.result import Result
from core.terminal.ghostty.platform.base import GhosttyPlatform

logger = logging.getLogger(__name__)

_BIN = "ghostty"


def _cmd(parts: list[str]) -> Result:
    """Выполняет внешнюю команду и возвращает единый Result."""
    try:
        proc = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        msg = f"Ghostty не установлен: не найден бинарник {_BIN!r}"
        logger.error(msg)
        return Result.failure(msg)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.exception("Не удалось выполнить ghostty: %s", exc)
        return Result.failure(f"Ошибка Ghostty: {exc}")

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "неизвестная ошибка").strip()
        logger.error("ghostty завершился с ошибкой: %s", message)
        return Result.failure(f"Ошибка Ghostty: {message}")

    logger.debug("ghostty выполнена успешно: %s", shlex.join(parts))
    return Result.success("Ghostty: окно/вкладка создана (Linux)")


def _extra_args(command: str | None, cwd: str | None) -> list[str]:
    """Дополнительные аргументы для команды ghostty (+ -e)."""
    args: list[str] = []
    if cwd:
        args += [f"--working-directory={cwd}"]
    if command:
        args += ["-e", command]
    return args


class GhosttyLinux(GhosttyPlatform):
    """Управление Ghostty на Linux."""

    def open_new_window(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        parts = [_BIN, "+new-window", *_extra_args(command, cwd)]
        logger.info("Открытие нового окна (command=%r, cwd=%r)", command, cwd)
        return _cmd(parts)

    def open_new_tab(
        self, command: str | None = None, cwd: str | None = None
    ) -> Result:
        parts = [_BIN, "+new-window", *_extra_args(command, cwd)]
        logger.info("Открытие новой вкладки (command=%r, cwd=%r)", command, cwd)
        return _cmd(parts)

    def focus(self) -> Result:
        logger.info("Запрос фокуса Ghostty на Linux")
        return Result.success("Ghostty: фокус (Linux)")