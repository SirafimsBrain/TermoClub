# termoclub/core/sessions/terminal/FletTerminalSession.py
"""Сессия внутреннего терминала на flet-terminal (нужен собранный клиент).

Символы ввода здесь отдаёт сам xterm.dart (он пропускает нажатия через
IME Flutter, поэтому кириллица и регистр работают), поэтому на Python
остаётся буфер обмена и размер окна PTY.

Размер берётся не из пикселей контейнера, а из события `on_resize` самого
контрола: Dart присылает уже готовые колонки и строки текущей сетки
xterm.dart (`{"cols": .., "rows": ..}`), гадать по кеглю не нужно.
Копирование — `Ctrl+Shift+C`/`Ctrl+Insert` (клиент отдаёт выделенный текст
событием `on_copy`), вставка — `Ctrl+V`/`Shift+Insert`/`Ctrl+Shift+V`
через `Terminal.paste()` (Dart читает системный буфер сам).
"""
from __future__ import annotations

import asyncio
import json
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

    #: Сколько ждать `on_mount` от Dart-контрола, прежде чем сообщить о проблеме.
    MOUNT_TIMEOUT = 2.0

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
        on_renderer_missing: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(title, session_id)
        self._bridge = PtyBridge(shell=shell, args=args, cwd=cwd, cols=cols, rows=rows)
        self._terminal: Terminal | None = None
        self._pump_future = None
        self._watchdog = None
        self._page: ft.Page | None = None
        self._clipboard = None
        self._mounted = False
        self.on_terminated = on_terminated
        #: Вызывается, если клиент не умеет рендерить `FletTerminal`.
        self.on_renderer_missing = on_renderer_missing

    @property
    def icon(self) -> str:
        return "terminal"

    def start(self, page: ft.Page) -> None:
        """Запускает PTY, pump-насос и проверку наличия Dart-контрола."""
        self._page = page
        self._status = SessionStatus.RUNNING
        self._pump_future = page.run_task(self._run)
        self._watchdog = page.run_task(self._check_renderer)
        logger.info("FletTerminalSession %s: started", self.session_id)

    async def _check_renderer(self) -> None:
        """Сообщает, если клиент без Dart-расширения (контрол не смонтировался).

        `FletTerminal` — Flutter-расширение: stock-клиент выводит «Unknown
        control: FletTerminal» и никогда не шлёт `on_mount`. Без этого теста
        вкладка оставалась бы пустой без объяснений.
        """
        await asyncio.sleep(self.MOUNT_TIMEOUT)
        self._watchdog = None
        if self._mounted or self._status == SessionStatus.CLOSED:
            return
        message = (
            "flet-terminal недоступен: клиент не содержит Dart-расширения "
            "(нужен `flet build`). Откройте Terminal (pyte)."
        )
        logger.warning("FletTerminalSession %s: %s", self.session_id, message)
        if self.on_renderer_missing is not None:
            self.on_renderer_missing(message)

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
                font_family="JetBrains Mono",
                cursor_blink=True,
                auto_focus=True,
                expand=True,
                on_data=self._on_terminal_data,
                on_resize=self._on_terminal_resize,
                on_copy=self._on_terminal_copy,
                on_mount=self._on_terminal_mount,
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

    def _on_terminal_resize(self, event: ft.ControlEvent) -> None:
        """xterm.dart сообщил свой реальный размер — подгоняем окно PTY."""
        data = getattr(event, "data", None)
        if not data:
            return
        try:
            size = json.loads(data) if isinstance(data, str) else dict(data)
            columns = int(size["cols"])
            lines = int(size["rows"])
        except (TypeError, ValueError, KeyError):
            logger.warning(
                "FletTerminalSession %s: bad resize payload %r",
                self.session_id,
                data,
            )
            return
        if columns <= 0 or lines <= 0:
            return
        self._bridge.resize(columns, lines)
        logger.info(
            "FletTerminalSession %s: xterm grid %dx%d",
            self.session_id,
            columns,
            lines,
        )

    def _on_terminal_copy(self, event: ft.ControlEvent) -> None:
        """xterm.dart уже положил выделение в буфер — фиксируем в логе."""
        logger.info("FletTerminalSession %s: copied selection", self.session_id)

    def _on_terminal_mount(self, event: ft.ControlEvent) -> None:
        """Dart-контрол жив и готов принимать байты."""
        self._mounted = True
        logger.info("FletTerminalSession %s: terminal control mounted", self.session_id)

    def handle_key(self, event: ft.KeyboardEvent) -> bool:
        """Перехватывает только буфер обмена.

        Остальные клавиши обрабатывает сам xterm.dart, поэтому в PTY
        ничего не дублируется.
        """
        if self._is_paste_shortcut(event):
            self.paste()
            return True
        if self._is_copy_shortcut(event):
            self.copy()
            return True
        return False

    def _is_paste_shortcut(self, event: ft.KeyboardEvent) -> bool:
        """Ctrl/⌘+V, Ctrl/⌘+Shift+V и Shift+Insert вставляют из буфера обмена."""
        if event.key not in _PASTE_KEYS:
            return False
        if event.key == "Insert":
            return event.shift
        return event.ctrl or event.meta

    def _is_copy_shortcut(self, event: ft.KeyboardEvent) -> bool:
        """Ctrl/⌘+Shift+C и Ctrl/⌘+Insert копируют выделение xterm.dart."""
        if not (event.ctrl or event.meta):
            return False
        if event.key == "Insert":
            return True
        return event.shift and event.key.upper() == "C"

    def copy(self) -> None:
        """Кладёт выделение xterm.dart в системный буфер обмена.

        Без выделения копировать нечего и `Ctrl+Shift+C` ничего не делает —
        как в обычном терминале (xterm.dart сам копирует выделение при
        правом клике и по своим шорткатам).
        """
        if self._page is None:
            logger.warning(
                "FletTerminalSession %s: no page for clipboard copy", self.session_id
            )
            return
        self._page.run_task(self._copy_selection)

    async def _copy_selection(self) -> None:
        terminal = self._terminal
        if terminal is None:
            return
        try:
            text = await terminal.get_selection_async()
        except Exception:  # noqa: BLE001 — контрол есть только в своём клиенте
            text = None
        if not text:
            logger.info(
                "FletTerminalSession %s: nothing selected to copy", self.session_id
            )
            return
        try:
            if self._clipboard is None:
                self._clipboard = ft.Clipboard()
            await self._clipboard.set(text)
        except Exception:  # noqa: BLE001 — сервис буфера есть не на всех платформах
            logger.warning(
                "FletTerminalSession %s: clipboard is not writable", self.session_id
            )
            return
        logger.info("FletTerminalSession %s: copied %d chars", self.session_id, len(text))

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
        """Отменяет pump и сторожевой таймер, убивает PTY (синхронно)."""
        for future in (self._pump_future, self._watchdog):
            if future is not None:
                try:
                    future.cancel()
                except RuntimeError:
                    pass
        self._pump_future = None
        self._watchdog = None
        self._bridge.request_stop()
        self._bridge.terminate()
        self._status = SessionStatus.CLOSED
        logger.info("FletTerminalSession %s: cleaned up", self.session_id)
