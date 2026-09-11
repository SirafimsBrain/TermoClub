# termoclub/core/sessions/terminal/TerminalSession.py
"""Сессия внутреннего терминала: PTY-процесс + рендер через pyte.

Работает со stock-клиентом Flet (чистый Python, без Dart-расширений):
экран эмулирует `pyte`, отображение — `ft.Text` моноширинным шрифтом,
ввод — через `page.on_keyboard_event` (диспетчер в `main.py`).
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable

import flet as ft
import pyte

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.PtyBridge import PtyBridge
from core.sessions.WorkspaceItem import WorkspaceItem

logger = logging.getLogger(__name__)

#: Моноширинный шрифт из локальных assets (`FontAwesome.FONTS`).
MONO_FONT = "JetBrains Mono"

#: Минимальный интервал перерисовки экрана (защита от UI-шторма).
REFRESH_MIN_INTERVAL = 0.05

_MODIFIER_ONLY = {
    "Shift",
    "Control",
    "Alt",
    "Meta",
    "Caps Lock",
    "Num Lock",
    "Scroll Lock",
    "Insert",
}

_SPECIALS = {
    "Enter": b"\r",
    "Backspace": b"\x7f",
    "Tab": b"\t",
    "Escape": b"\x1b",
    "Delete": b"\x1b[3~",
    "Home": b"\x1b[H",
    "End": b"\x1b[F",
    "Page Up": b"\x1b[5~",
    "Page Down": b"\x1b[6~",
    "Arrow Up": b"\x1b[A",
    "Arrow Down": b"\x1b[B",
    "Arrow Right": b"\x1b[C",
    "Arrow Left": b"\x1b[D",
    " ": b" ",
    "Space": b" ",
    "F1": b"\x1bOP",
    "F2": b"\x1bOQ",
    "F3": b"\x1bOR",
    "F4": b"\x1bOS",
    "F5": b"\x1b[15~",
    "F6": b"\x1b[17~",
    "F7": b"\x1b[18~",
    "F8": b"\x1b[19~",
    "F9": b"\x1b[20~",
    "F10": b"\x1b[21~",
    "F11": b"\x1b[23~",
    "F12": b"\x1b[24~",
}


def key_to_bytes(
    key: str,
    shift: bool = False,
    ctrl: bool = False,
    alt: bool = False,
    meta: bool = False,
) -> bytes | None:
    """Маппит клавишу (с модификаторами) в байты для PTY."""
    if key in _MODIFIER_ONLY:
        return None
    if ctrl or meta:
        if len(key) == 1 and key.isalpha():
            return bytes([ord(key.lower()) - 96])  # Ctrl+C -> 0x03 и т.д.
        return None
    if alt and len(key) == 1:
        return b"\x1b" + key.encode("utf-8", errors="ignore")
    if key in _SPECIALS:
        return _SPECIALS[key]
    if len(key) == 1:
        return key.encode("utf-8", errors="ignore")
    return None


class TerminalSession(WorkspaceItem):
    """Вкладка внутреннего терминала (pyte-рендер, работает везде)."""

    KIND = "terminal"

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
        self._screen = pyte.HistoryScreen(cols, rows, history=1000)
        self._stream = pyte.Stream(self._screen)
        self._text: ft.Text | None = None
        self._last_refresh = 0.0
        self._pump_future = None
        self.on_terminated = on_terminated

    @property
    def icon(self) -> str:
        return "terminal"

    @property
    def display_text(self) -> str:
        """Текущий видимый текст экрана (для тестов и отладки)."""
        return "\n".join(self._screen.display)

    def start(self, page: ft.Page) -> None:
        """Запускает PTY и pump-насос задачей UI-цикла."""
        self._status = SessionStatus.RUNNING
        self._pump_future = page.run_task(self._run)
        logger.info("TerminalSession %s: started", self.session_id)

    async def _run(self) -> None:
        try:
            await self._bridge.start()
            await self._bridge.pump(self._on_pty_data)
        except OSError as exc:
            self._status = SessionStatus.ERROR
            logger.error("TerminalSession %s: %s", self.session_id, exc)
            self._feed_text(f"\r\n[terminal error: {exc}]\r\n")
            self._refresh(force=True)
            return
        self._status = SessionStatus.CLOSED
        self._refresh(force=True)
        logger.info("TerminalSession %s: shell exited", self.session_id)
        if self.on_terminated is not None:
            self.on_terminated(self.session_id)

    def _on_pty_data(self, chunk: bytes) -> None:
        self._feed_text(chunk.decode("utf-8", errors="replace"))
        self._refresh()

    def _feed_text(self, text: str) -> None:
        self._stream.feed(text)

    def _refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_refresh < REFRESH_MIN_INTERVAL:
            return
        self._last_refresh = now
        if self._text is not None:
            self._text.value = self.display_text or " "
            try:
                self._text.update()
            except RuntimeError:
                pass  # Контрол ещё не примонтирован к странице.

    def get_content(self) -> ft.Control:
        """Строит (один раз) прокручиваемое моноширинное поле экрана."""
        if self._content is None:
            self._text = ft.Text(
                value=" ",
                font_family=MONO_FONT,
                size=13,
                no_wrap=True,
            )
            self._content = ft.Container(
                bgcolor=ft.Colors.BLACK,
                padding=8,
                expand=True,
                content=ft.ListView(
                    [self._text],
                    expand=True,
                    auto_scroll=True,
                    spacing=0,
                    padding=0,
                ),
            )
        return self._content

    def handle_key(self, event: ft.KeyboardEvent) -> bool:
        """Отправляет клавишу в PTY. True, если клавиша поглощена."""
        data = key_to_bytes(
            event.key,
            shift=event.shift,
            ctrl=event.ctrl,
            alt=event.alt,
            meta=event.meta,
        )
        if data is None:
            return False
        self._bridge.write(data)
        return True

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
        self._refresh(force=True)
        self._status = SessionStatus.CLOSED
        logger.info("TerminalSession %s: cleaned up", self.session_id)
