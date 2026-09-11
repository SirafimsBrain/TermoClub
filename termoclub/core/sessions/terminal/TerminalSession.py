# termoclub/core/sessions/terminal/TerminalSession.py
"""Сессия внутреннего терминала: PTY + pyte + Flet.

Работает со stock-клиентом Flet (чистый Python, без Dart-расширений)
и занимается только оркестрацией:

* `PtyBridge` — псевдотерминал и шелл (запуск, запись, чтение, размер);
* `PyteScreen` — эмуляция VT100/ANSI (сетка ячеек, курсор, resize);
* `TerminalView` — контролы Flet (экран со спанами, скрытое поле ввода);
* `TerminalKeymap` и `TextInputBridge` — раскладка и текстовый ввод.

Ввод разделён на два канала. `KeyboardEvent.key` во Flet — это
`LogicalKeyboardKey.keyLabel`: логическая (US) метка клавиши в верхнем
регистре, без учёта раскладки и модификаторов, поэтому:

* служебные клавиши и `Ctrl+<буква>` приходят из `page.on_keyboard_event`
  (диспетчер в `main.py`) — для них метки достаточно;
* настоящие символы (кириллица, регистр, AltGr, IME, вставка) — только из
  скрытого поля ввода `TerminalView`.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable

import flet as ft

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.PtyBridge import PtyBridge
from core.sessions.terminal.PyteScreen import PyteScreen
from core.sessions.terminal.TerminalKeymap import TerminalKeymap
from core.sessions.terminal.TerminalView import TerminalView
from core.sessions.WorkspaceItem import WorkspaceItem

logger = logging.getLogger(__name__)


class TerminalSession(WorkspaceItem):
    """Вкладка внутреннего терминала (pyte-рендер, работает везде)."""

    KIND = "terminal"

    #: Минимальный интервал перерисовки экрана (защита от UI-шторма).
    REFRESH_MIN_INTERVAL = 0.05

    #: Клавиши, которые отдаются скрытому полю ввода (Enter -> on_submit).
    TEXT_FIELD_KEYS = frozenset({"Enter", " "})

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
        self._screen = PyteScreen(cols, rows)
        self._view = TerminalView(on_bytes=self._send_input, on_resize=self.resize)
        self._page: ft.Page | None = None
        self._clipboard = None
        self._last_refresh = 0.0
        self._pump_future = None
        self.on_terminated = on_terminated

    @property
    def icon(self) -> str:
        return "terminal"

    @property
    def display_text(self) -> str:
        """Текущий видимый текст экрана (для тестов и отладки)."""
        return self._screen.text()

    # --- Жизненный цикл ---

    def start(self, page: ft.Page) -> None:
        """Запускает PTY и pump-насос задачей UI-цикла."""
        self._page = page
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
            self._screen.feed(f"\r\n[terminal error: {exc}]\r\n")
            self._refresh(force=True)
            return
        self._status = SessionStatus.CLOSED
        self._refresh(force=True)
        logger.info("TerminalSession %s: shell exited", self.session_id)
        if self.on_terminated is not None:
            self.on_terminated(self.session_id)

    def get_content(self) -> ft.Control:
        """Строит (один раз) контролы терминала вью."""
        if self._content is None:
            self._content = self._view.control
        return self._content

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

    # --- Вывод PTY -> экран ---

    def _on_pty_data(self, chunk: bytes) -> None:
        self._screen.feed_bytes(chunk)
        self._refresh()

    def _send_input(self, data: bytes) -> None:
        """Пишет байты пользовательского ввода в PTY."""
        self._bridge.write(data)

    def _refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_refresh < self.REFRESH_MIN_INTERVAL:
            return
        self._last_refresh = now
        self._view.render(self._screen)

    # --- Размер ---

    def resize(self, columns: int, lines: int) -> None:
        """Подгоняет экран и окно PTY под новый размер (шелл получит SIGWINCH)."""
        if not self._screen.resize(columns, lines):
            return
        self._bridge.resize(columns, lines)
        self._refresh(force=True)
        logger.info(
            "TerminalSession %s: resized to %dx%d", self.session_id, columns, lines
        )

    # --- Ввод: служебные клавиши через page.on_keyboard_event ---

    def handle_key(self, event: ft.KeyboardEvent) -> bool:
        """Отправляет клавишу в PTY. True, если клавиша поглощена."""
        if self._is_own_paste(event):
            self.paste()
            return True
        if self._belongs_to_text_field(event):
            return False
        data = TerminalKeymap.to_bytes(
            event.key,
            shift=event.shift,
            ctrl=event.ctrl,
            alt=event.alt,
            meta=event.meta,
        )
        if data is None:
            return False
        self._bridge.write(data)
        if event.key == "Tab":
            self.focus_input()  # Tab уводит фокус из поля ввода — возвращаем.
        return True

    def _belongs_to_text_field(self, event: ft.KeyboardEvent) -> bool:
        """True, если ввод придёт из скрытого поля, а не из KeyboardEvent.

        Без поля ввода (например, до `get_content()`) деградируем к
        старому поведению: печатаемые символы обрабатывает диспетчер.
        """
        if not self._view.input_ready:
            return False
        # Ctrl/⌘+V вставляет текст средствами самого поля ввода (Shift-вариант
        # перехватывает сама сессия — см. `_is_own_paste`).
        if event.key.upper() == "V" and (event.ctrl or event.meta):
            return True
        if event.key == "Insert":
            return event.shift
        # Управляющие комбинации символов в поле не печатаются.
        if event.ctrl or event.meta:
            return False
        return event.key in self.TEXT_FIELD_KEYS or len(event.key) == 1

    def _is_own_paste(self, event: ft.KeyboardEvent) -> bool:
        """Ctrl/⌘+Shift+V — а без поля ввода ещё Ctrl/⌘+V и Shift+Insert.

        Обычные `Ctrl+V` и `Shift+Insert` намеренно не перехватываются: их
        обрабатывает само поле ввода, иначе вставка случилась бы дважды.
        """
        if event.key == "Insert":
            return event.shift and not self._view.input_ready
        if event.key.upper() != "V" or not (event.ctrl or event.meta):
            return False
        return event.shift or not self._view.input_ready

    # --- Буфер обмена ---

    def paste(self) -> None:
        """Просит вставить в PTY текст из системного буфера обмена."""
        if self._page is None:
            logger.warning(
                "TerminalSession %s: no page for clipboard paste", self.session_id
            )
            return
        try:
            self._page.run_task(self._paste_from_clipboard)
        except (AttributeError, RuntimeError):
            logger.warning(
                "TerminalSession %s: clipboard paste is not available", self.session_id
            )

    async def _paste_from_clipboard(self) -> None:
        try:
            if self._clipboard is None:
                self._clipboard = ft.Clipboard()
            text = await self._clipboard.get()
        except Exception:  # noqa: BLE001 — сервис буфера есть не на всех платформах
            logger.warning(
                "TerminalSession %s: clipboard is not readable", self.session_id
            )
            return
        if not text:
            return
        self._view.clear_input()
        self._send_input(text.encode("utf-8"))
        self.focus_input()
        logger.info("TerminalSession %s: pasted %d chars", self.session_id, len(text))

    # --- Фокус ---

    def focus_input(self) -> None:
        """Возвращает фокус скрытому полю ввода (иначе IME-символы не придут)."""
        if not self._view.input_ready or self._page is None:
            return
        try:
            self._page.run_task(self._view.focus_input)
        except (AttributeError, RuntimeError):
            pass  # Контрол ещё не примонтирован к странице.

    def on_focus(self) -> None:
        super().on_focus()
        self.focus_input()
