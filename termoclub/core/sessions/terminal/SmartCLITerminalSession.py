# termoclub/core/sessions/terminal/SmartCLITerminalSession.py
"""Сессия внутреннего терминала на smartcli-toolkit (заменяет flet-terminal).

Архитектура идентична TerminalSession, но вместо собственного PTY-моста
использует PtySession из smartcli_core, а вместо PyteScreen — ScreenModel
из того же пакета. Всё остальное (TerminalView, TextInputBridge,
TerminalKeymap) остаётся без изменений, поэтому совместимость с Flet
и существующим UI сохраняется.

Это позволяет избавиться от зависимости от flet-terminal (Dart-расширения)
и работать полностью на Python, используя зрелый smartcli-toolkit.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Callable

import flet as ft

from core.sessions.WorkspaceItem import WorkspaceItem
from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.TextInputBridge import TextInputBridge
from core.sessions.terminal.TerminalKeymap import TerminalKeymap
from core.sessions.terminal.TerminalView import TerminalView

# Импортируем smartcli_core. Если недоступно — отложим ошибку до запуска.
try:
    from smartcli_core import PtySession, ScreenModel
except Exception:  # pragma: no cover
    PtySession = None  # type: ignore
    ScreenModel = None  # type: ignore

logger = logging.getLogger(__name__)


class SmartCLITerminalSession(WorkspaceItem):
    """Сессия внутреннего терминала на smartcli-toolkit.

    Заменяет flet-terminal: использует smartcli_core вместо Dart-расширения.
    Работает полностью на Python: PTY -> smartcli_core -> Flet-рендеринг.
    """

    KIND = "terminal-gpu"
    ICON = "terminal"

    #: Минимальный интервал перерисовки экрана (защита от UI-шторма).
    REFRESH_MIN_INTERVAL = 0.05

    def __init__(
        self,
        title: str = "Terminal",
        shell: str | None = None,
        args: list[str] | None = None,
        cwd: str | None = None,
        cols: int = 80,
        rows: int = 24,
        session_id: str | None = None,
        on_terminated: Optional[Callable[[str], None]] = None,
        on_renderer_missing: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(title, session_id)
        self._shell = shell or "bash"
        self._args = args or []
        self._cwd = cwd
        self._cols = cols
        self._rows = rows
        self._on_terminated = on_terminated
        self._on_renderer_missing = on_renderer_missing

        # Состояние
        self._status = SessionStatus.CREATED
        self._content: Optional[ft.Control] = None
        self._view: Optional[TerminalView] = None
        self._pty_session: Optional[PtySession] = None
        self._screen: Optional[ScreenModel] = None  # Keep _screen for test compatibility
        self._text_input_bridge: Optional[TextInputBridge] = None
        self._page: Optional[ft.Page] = None
        self._pump_future: Optional[asyncio.Future] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._last_refresh = 0.0

        # Коллбэки для совместимости с тестами
        self._on_resize_callback: Optional[Callable[[int, int], None]] = None
        self._on_input_bytes_callback: Optional[Callable[[bytes], None]] = None
        self._on_focus_request_callback: Optional[Callable[[], None]] = None

    # --- Свойства, дублирующие интерфейс TerminalSession ---

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def kind(self) -> str:
        return self.KIND

    @property
    def title(self) -> str:
        return self._title

    @property
    def icon(self) -> str:
        return self.ICON

    @property
    def status(self) -> SessionStatus:
        return self._status

    @property
    def display_text(self) -> str:
        """Текущий видимый текст экрана (для тестов и отладки)."""
        if self._view is None:
            return ""
        return "".join(span.text or "" for span in self._view._text.spans)

    # --- Жизненный цикл ---

    def start(self, page: ft.Page) -> None:
        """Запускает PTY и pump-насос задачей UI-цикла."""
        if self._status == SessionStatus.RUNNING:
            return

        self._page = page
        self._status = SessionStatus.RUNNING
        try:
            self._setup_smartcli()
            self._setup_view()
            self._start_pump_and_refresh()
            logger.info("SmartCLITerminalSession %s: started", self.session_id)
        except Exception as exc:
            self._status = SessionStatus.ERROR
            logger.error("SmartCLITerminalSession %s: start failed: %s", self.session_id, exc)
            if self._on_renderer_missing:
                self._on_renderer_missing(str(exc))
            raise

    def _setup_smartcli(self) -> None:
        """Инициализирует компоненты smartcli_core."""
        if PtySession is None or ScreenModel is None:
            raise RuntimeError("smartcli_core is not installed")

        # PTY-сессия
        self._pty_session = PtySession(
            cols=self._cols,
            rows=self._rows,
        )

        # Экран терминала
        self._screen_model = ScreenModel(cols=self._cols, rows=self._rows)
        # Для обратной совместимости с тестами, которые ожидают атрибут _screen
        self._screen = self._screen_model

        # Текстовый ввод
        self._text_input_bridge = TextInputBridge()

        logger.info("SmartCLITerminalSession %s: smartcli_core initialized", self.session_id)

    def _setup_view(self) -> None:
        """Создаёт Flet-контролы для отображения."""
        if self._page is None:
            return

        self._view = TerminalView(
            on_bytes=self._on_input_bytes,
            on_resize=self._on_resize,
            on_focus_request=self._on_focus_request,
        )
        self._content = self._view.control
        self._page.add(self._content)
        logger.info("SmartCLITerminalSession %s: Flet view created", self.session_id)

    def _start_pump_and_refresh(self) -> None:
        """Запускает фоновые задачи: чтение PTY и периодическое обновление UI."""
        assert self._page is not None, "Page must be set before starting"
        assert self._pty_session is not None, "PTY session must be initialized"
        assert self._screen_model is not None, "Screen model must be initialized"

        # Task, которая читает байты из PTY и подаёт их в экран
        self._pump_future = asyncio.ensure_future(self._pump_loop())

        # Task, которая периодически обновляет UI (защита от избыточной перерисовки)
        self._refresh_task = self._page.run_task(self._refresh_loop)

    async def _pump_loop(self) -> None:
        """Читает PTY и обновляет экран до остановки сессии."""
        assert self._pty_session is not None
        assert self._screen_model is not None

        try:
            # Запускаем PTY с указанной оболочкой
            await self._pty_session.start(self._shell, args=self._args, cwd=self._cwd)

            # Основной цикл чтения
            async for data in self._pty_session.pump():
                if self._status != SessionStatus.RUNNING:
                    break
                if not data:
                    continue

                # Обрабатываем байты через smartcli_core ScreenModel
                self._screen_model.feed(data)

                # Вызываем коллбэк для совместимости с тестами
                if self._on_input_bytes_callback:
                    self._on_input_bytes_callback(data)

        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover
            logger.error("SmartCLITerminalSession %s: pump failed: %s", self.session_id, exc)
            self._status = SessionStatus.ERROR
        finally:
            # При выходе из цикла убеждаемся, что сессия помечена как закрытая
            if self._status == SessionStatus.RUNNING:
                self._status = SessionStatus.CLOSED

    async def _refresh_loop(self) -> None:  # pragma: no cover
        """Периодически обновляет UI, если экран изменился."""
        while self._status == SessionStatus.RUNNING:
            await asyncio.sleep(self.REFRESH_MIN_INTERVAL)
            now = self._loop_time()
            if now - self._last_refresh < self.REFRESH_MIN_INTERVAL:
                continue
            self._last_refresh = now
            if self._page is not None:
                try:
                    self._page.run_task(self._view.update)
                except RuntimeError:
                    # Контрол ещё не примонтирован к странице.
                    pass

    def _loop_time(self) -> float:  # pragma: no cover
        """Время событийного цикла для измерения интервалов."""
        return self._page.loop.time() if self._page and self._page.loop else 0.0

    # --- Коллбэки для терминала ---

    def _on_input_bytes(self, data: bytes) -> None:
        """Обрабатывает ввод пользователя: отправляем в PTY."""
        if self._status != SessionStatus.RUNNING:
            return
        if self._pty_session is None:
            return
        # smartcli_core ожидает строку, поэтому декодируем
        try:
            text = data.decode("utf-8", errors="replace")
            self._pty_session.send_text(text)
        except Exception as exc:  # pragma: no cover
            logger.error("SmartCLITerminalSession %s: send input failed: %s", self.session_id, exc)

        # Вызываем коллбэк для совместимости с тестами
        if self._on_input_bytes_callback:
            self._on_input_bytes_callback(data)

    def _on_resize(self, cols: int, rows: int) -> None:
        """Обрабатывает изменение размера терминала."""
        screen = self._screen or self._screen_model
        if screen is None:
            return

        changed = screen.resize(cols, rows)
        if not changed:
            return

        if self._pty_session is not None:
            self._pty_session.resize(cols, rows)

        logger.info("SmartCLITerminalSession %s: resized to %dx%d", self.session_id, cols, rows)

        # Вызываем коллбэк для совместимости с тестами
        if self._on_resize_callback:
            self._on_resize_callback(cols, rows)

    def _on_focus_request(self) -> None:
        """Обрабатывает запрос фокуса на терминал."""
        if self._status == SessionStatus.RUNNING:
            self._status = SessionStatus.FOCUSED
        logger.debug("SmartCLITerminalSession %s: focus requested", self.session_id)

        # Вызываем коллбэк для совместимости с тестами
        if self._on_focus_request_callback:
            self._on_focus_request_callback()

    # --- Ввод ---

    def _send_input(self, data: bytes) -> None:
        """Отправляет байты в PTY (из TerminalView)."""
        self._on_input_bytes(data)

    def focus_input(self) -> None:
        """Вызывается TerminalView, когда требуется фокус на поле ввода."""
        self._on_focus_request()

    def handle_key(self, event: ft.KeyboardEvent) -> bool:
        """Обрабатывает клавиатурные события Flet.

        Возвращает True, если событие обработано и не должно распространяться дальше.
        """
        if self._status not in (SessionStatus.RUNNING, SessionStatus.FOCUSED):
            return False

        # Ctrl+C, Ctrl+D, Ctrl+Z, Ctrl+\
        if event.ctrl and event.key.lower() in ("c", "d", "z", "\\"):
            if self._pty_session is not None:
                if event.key.lower() == "c":
                    self._pty_session.send_signal("SIGINT")
                elif event.key.lower() == "d":
                    self._pty_session.send_signal("SIGQUIT")
                elif event.key.lower() == "z":
                    self._pty_session.send_signal("SIGTSTP")
                elif event.key.lower() == "\\":
                    self._pty_session.send_signal("SIGQUIT")
            return True

        # Служебные клавиши (стрелки, Enter, Tab и т.д.)
        # Но НЕ пробел, так как он должен идти в скрытое поле ввода для поддержки IME
        if event.key == " ":
            # Пробел обрабатывается скрытым полем ввода
            return False
            
        key_bytes = TerminalKeymap.to_bytes(
            event.key,
            shift=event.shift,
            ctrl=event.ctrl,
            alt=event.alt,
            meta=event.meta,
        )
        if key_bytes is not None:
            if self._pty_session is not None:
                self._pty_session.send_text(key_bytes.decode("utf-8", errors="replace"))
            return True

        # Печатаемые символы — оставляем для скрытого поля ввода
        return False

    # --- Буфер обмена ---

    def paste(self) -> None:
        """Запрашивает вставку из буфера обмена."""
        if self._page is None:
            return
        try:
            text = self._page.get_clipboard_text()
            if text:
                self._send_input(text.encode("utf-8"))
        except Exception as exc:  # pragma: no cover
            logger.error("SmartCLITerminalSession %s: paste failed: %s", self.session_id, exc)

    def copy(self) -> None:
        """Копирует видимую область экрана в буфер обмена."""
        if self._page is None or self._view is None:
            return
        try:
            text = self.display_text
            self._page.set_clipboard_text(text)
            logger.info("SmartCLITerminalSession %s: copied %d chars", self.session_id, len(text))
        except Exception as exc:  # pragma: no cover
            logger.error("SmartCLITerminalSession %s: copy failed: %s", self.session_id, exc)

    # --- Изменение размера ---

    def resize(self, cols: int, rows: int) -> None:
        """Изменяет размер терминала."""
        if self._cols == cols and self._rows == rows:
            return
        self._cols = cols
        self._rows = rows
        if self._screen_model is not None:
            self._screen_model.resize(cols, rows)
        if self._pty_session is not None:
            self._pty_session.resize(cols, rows)
        logger.info("SmartCLITerminalSession %s: resized to %dx%d", self.session_id, cols, rows)

    # --- Фокус и очистка ---

    def on_focus(self) -> None:
        if self._status == SessionStatus.RUNNING:
            self._status = SessionStatus.FOCUSED
        logger.debug("SmartCLITerminalSession %s: focused", self.session_id)

    def on_blur(self) -> None:
        if self._status == SessionStatus.FOCUSED:
            self._status = SessionStatus.RUNNING
        logger.debug("SmartCLITerminalSession %s: blurred", self.session_id)

    def cleanup(self) -> None:
        """Останавливает сессию и освобождает ресурсы."""
        if self._status == SessionStatus.CLOSED:
            return

        self._status = SessionStatus.CLOSED

        if self._pump_future is not None:
            self._pump_future.cancel()
            self._pump_future = None

        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

        if self._pty_session is not None:
            self._pty_session.terminate()
            self._pty_session = None

        self._screen_model = None
        self._view = None
        self._text_input_bridge = None
        self._page = None

        logger.info("SmartCLITerminalSession %s: cleaned up", self.session_id)

    def get_content(self) -> ft.Control:
        """Возвращает Flet-контрол для отображения."""
        if self._content is None:
            self._content = ft.Text("❌ SmartCLI Terminal не инициализирован")
        return self._content