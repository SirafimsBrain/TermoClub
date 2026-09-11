# termoclub/core/sessions/terminal/FletTerminalSession.py
"""Сессия внутреннего терминала на flet-terminal (нужен собранный клиент).

Символы ввода здесь отдаёт сам xterm.dart (он пропускает нажатия через
IME Flutter, поэтому кириллица и регистр работают), поэтому на Python
остаётся только вставка из буфера обмена: у контрола нет своего
клавиатурного диспетчера, и `Ctrl+V` до него не доходит.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

import flet as ft
from flet_terminal import Terminal

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.PtyBridge import PtyBridge
from core.sessions.WorkspaceItem import WorkspaceItem

logger = logging.getLogger(__name__)

#: Клавиши со «вставкой» из системного буфера обмена.
_PASTE_KEYS = {"V", "Insert"}


class FletTerminalSession(WorkspaceItem):
    """Вкладка внутреннего терминала на flet-terminal.

    Работает только в клиенте, собранном через `flet build` (Dart-расширение).
    Логика (PTY) живёт в `PtyBridge`, отображение — в `Terminal`.
    Pump запущенного шелла выполняется задачей UI-цикла через
    `page.run_task()`; завершение шелла закрывает вкладку через колбэк.
    """

    KIND = "terminal-gpu"

    def __init__(
        self,
        title: str = "Terminal",
        shell: str | None = None,
        args: list[str] | None = None,
        cwd: str | None = None,
        cols: int = 80,
        rows: int = 24,
        session_id: str | None = None,
        on_terminated: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(title, session_id)
        self._bridge = PtyBridge(shell=shell, args=args, cwd=cwd, cols=cols, rows=rows)
        self._terminal: Terminal | None = None
        self._pump_future = None
        self._page: ft.Page | None = None
        self.on_terminated = on_terminated

    @property
    def icon(self) -> str:
        return "terminal"

    def start(self, page: ft.Page) -> None:
        """Запускает PTY и pump-насос задачей UI-цикла."""
        self._page = page
        self._status = SessionStatus.RUNNING
        self._pump_future = page.run_task(self._run)
        logger.info("FletTerminalSession %s: started", self.session_id)

    async def _run(self) -> None:
        try:
            await self._bridge.start()
            await self._bridge.pump(self._on_pty_data)
        except OSError as exc:
            self._status = SessionStatus.ERROR
            logger.error("FletTerminalSession %s: %s", self.session_id, exc)
            self._write_text(f"\r\n[terminal error: {exc}]\r\n")
            return
        self._status = SessionStatus.CLOSED
        logger.info("FletTerminalSession %s: shell exited", self.session_id)
        if self.on_terminated is not None:
            self.on_terminated(self.session_id)

    def _on_pty_data(self, chunk: bytes) -> None:
        if self._terminal is not None:
            self._terminal.write(chunk)

    def _write_text(self, text: str) -> None:
        if self._terminal is not None:
            self._terminal.write(text)

    def get_content(self) -> ft.Control:
        """Строит (один раз) контрол терминала и связывает ввод с PTY."""
        if self._terminal is None:
            self._terminal = Terminal(
                font_size=13.0,
                cursor_blink=True,
                expand=True,
                on_data=self._on_terminal_data,
            )
            self._terminal.set_on_bytes(self._on_user_input)
        if self._content is None:
            self._content = self._terminal
        return self._content

    def _on_user_input(self, data: bytes) -> None:
        self._bridge.write(data)

    def _on_terminal_data(self, event: ft.ControlEvent) -> None:
        """Строковый канал ввода — используется, пока не открыт DataChannel."""
        data = getattr(event, "data", None)
        if data:
            self._bridge.write(str(data).encode("utf-8"))

    def handle_key(self, event: ft.KeyboardEvent) -> bool:
        """Перехватывает только вставку из буфера обмена.

        Остальные клавиши обрабатывает сам xterm.dart, поэтому в PTY
        ничего не дублируется.
        """
        if not self._is_paste_shortcut(event):
            return False
        self.paste()
        return True

    def _is_paste_shortcut(self, event: ft.KeyboardEvent) -> bool:
        """Ctrl/⌘+V, Ctrl/⌘+Shift+V и Shift+Insert вставляют из буфера обмена."""
        if event.key not in _PASTE_KEYS:
            return False
        if event.key == "Insert":
            return event.shift
        return event.ctrl or event.meta

    def paste(self) -> None:
        """Просит Dart-сторону прочитать системный буфер обмена и отдать его в PTY."""
        terminal = self._terminal
        if terminal is None or not hasattr(terminal, "paste"):
            logger.warning(
                "FletTerminalSession %s: clipboard paste is not available",
                self.session_id,
            )
            return
        terminal.paste()
        logger.info("FletTerminalSession %s: paste requested", self.session_id)

    def on_focus(self) -> None:
        super().on_focus()
        if self._terminal is not None:
            try:
                self._terminal.focus()
            except RuntimeError:
                pass  # Контрол ещё не примонтирован к странице.

    def cleanup(self) -> None:
        """Отменяет pump, убивает PTY (синхронно)."""
        if self._pump_future is not None:
            try:
                self._pump_future.cancel()
            except RuntimeError:
                pass
            self._pump_future = None
        self._bridge.request_stop()
        self._bridge.terminate()
        self._status = SessionStatus.CLOSED
        logger.info("FletTerminalSession %s: cleaned up", self.session_id)
