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

Flet подписывается на клавиатуру глобальным `HardwareKeyboard.addHandler`
(`page.dart`), поэтому событие приходит и при сфокусированном поле: каналы
различаются по `TerminalView.input_focused`, иначе каждый символ дублировался
бы.

Буфер обмена: `Ctrl+V`/`Shift+Insert` вставляют (при сфокусированном поле —
силами самого поля), `Ctrl+Shift+V` — через `ft.Clipboard`; `Ctrl+Shift+C` и
`Ctrl+Insert` копируют видимую область экрана. Обычный `Ctrl+C` остаётся
SIGINT для шелла.

Движок (`PtyBridge` + `PyteScreen`) создаётся фабриками `_create_bridge()`
и `_create_screen()`. Наследник подменяет только их — например,
`SmartCLITerminalSession` берёт PTY и экран из smartcli-toolkit, — а вся
логика ввода, буфера обмена, троттлинга и размера остаётся общей.
"""
from __future__ import annotations

import asyncio
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

    #: «Тишина» после последнего resize-события, прежде чем менять сетку (сек).
    RESIZE_DEBOUNCE = 0.12

    #: Предел ожидания при непрерывном изменении размера (сек).
    RESIZE_MAX_WAIT = 0.3

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
        self._bridge = self._create_bridge(shell, args, cwd, cols, rows)
        self._screen = self._create_screen(cols, rows)
        self._view = TerminalView(
            on_bytes=self._send_input,
            on_resize=self.resize,
            on_focus_request=self.focus_input,
        )
        self._page: ft.Page | None = None
        self._clipboard = None
        self._last_refresh = 0.0
        self._pump_future = None
        self._refresh_task = None
        self._resize_task = None
        self._pending_size: tuple[int, int] | None = None
        self._pending_at = 0.0
        self.on_terminated = on_terminated

    @property
    def icon(self) -> str:
        return "terminal"

    @property
    def display_text(self) -> str:
        """Текущий видимый текст экрана (для тестов и отладки)."""
        return self._screen.text()

    # --- Движок (фабрики для наследников) ---

    def _create_bridge(
        self,
        shell: str | None,
        args: list[str] | None,
        cwd: str | None,
        cols: int,
        rows: int,
    ) -> PtyBridge:
        """Создаёт мост к PTY (по умолчанию — собственный `PtyBridge`)."""
        return PtyBridge(shell=shell, args=args, cwd=cwd, cols=cols, rows=rows)

    def _create_screen(self, columns: int, lines: int) -> PyteScreen:
        """Создаёт экран терминала (по умолчанию — `PyteScreen`).

        Вызывается после `_create_bridge()`, поэтому наследник может
        построить экран поверх только что созданного моста.
        """
        return PyteScreen(columns, lines)

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
        """Строит (один раз) контролы терминала вью.

        Сразу после сборки экран рисуется из текущего буфера: приглашение
        шелла успевает прийти до монтирования контрола, а новых данных от
        PTY может уже не быть (`bash` ждёт ввода) — без этой отрисовки
        терминал оставался бы пустым.
        """
        if self._content is None:
            self._content = self._view.control
            self._refresh(force=True)
        return self._content

    def cleanup(self) -> None:
        """Отменяет pump, убивает PTY (синхронно)."""
        for future in (self._pump_future, self._refresh_task, self._resize_task):
            if future is not None:
                try:
                    future.cancel()
                except RuntimeError:
                    pass
        self._pump_future = None
        self._refresh_task = None
        self._resize_task = None
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
            self._schedule_refresh()
            return
        self._last_refresh = now
        self._view.render(self._screen)

    def _schedule_refresh(self) -> None:
        """Планирует отрисовку, если чанк вывода попал в окно троттлинга.

        Без этого хвост вывода (например, приглашение шелла) остаётся
        только в буфере pyte и ждёт следующего чанка, которого может и не
        быть — шелл просто ждёт ввода, а экран остаётся пустым.
        """
        if self._refresh_task is not None or self._page is None:
            return
        self._refresh_task = self._page.run_task(self._flush_refresh)

    async def _flush_refresh(self) -> None:
        await asyncio.sleep(self.REFRESH_MIN_INTERVAL)
        self._refresh_task = None
        self._refresh(force=True)

    # --- Размер ---

    def resize(self, columns: int, lines: int) -> None:
        """Подгоняет экран и окно PTY под новый размер (шелл получит SIGWINCH).

        Событие приходит на каждом кадре анимации выдвижных панелей (300 мс),
        поэтому первый размер применяется сразу (интерфейс отзывчив), а
        остальные — один раз, когда раскладка успокоится. Иначе одно
        открытие/закрытие панели слало бы шеллу десятки SIGWINCH и столько же
        раз перерисовывало всю сетку: отсюда были и рваная отрисовка, и
        разъехавшееся приглашение шелла после каждого ресайза.
        """
        target = (columns, lines)
        if target == self._pending_size:
            return  # тот же размер: повтор кадров анимации
        self._pending_size = target
        self._pending_at = time.monotonic()
        if self._resize_task is not None:
            return  # хвостовое применение уже запланировано
        self._apply_resize(columns, lines)
        if self._page is not None:
            self._resize_task = self._page.run_task(self._flush_resize)

    def _apply_resize(self, columns: int, lines: int) -> None:
        """Применяет размер к экрану и PTY (без ожидания «тишины»)."""
        if not self._screen.resize(columns, lines):
            return
        self._bridge.resize(columns, lines)
        self._refresh(force=True)
        logger.info(
            "TerminalSession %s: resized to %dx%d", self.session_id, columns, lines
        )

    async def _flush_resize(self) -> None:
        """Применяет последний размер, когда поток resize-событий иссяк.

        Ждём «тишины» в `RESIZE_DEBOUNCE`, но не дольше `RESIZE_MAX_WAIT`:
        анимация панелей (300 мс) схлопывается в одно применение, а
        непрерывное перетаскивание окна всё равно обновляет сетку.
        """
        started = time.monotonic()
        try:
            while True:
                await asyncio.sleep(self.RESIZE_DEBOUNCE)
                if self._status == SessionStatus.CLOSED:
                    return
                quiet = time.monotonic() - self._pending_at >= self.RESIZE_DEBOUNCE
                if quiet or time.monotonic() - started >= self.RESIZE_MAX_WAIT:
                    break
            if self._pending_size is not None:
                self._apply_resize(*self._pending_size)
        finally:
            self._resize_task = None

    # --- Ввод: служебные клавиши через page.on_keyboard_event ---

    def handle_key(self, event: ft.KeyboardEvent) -> bool:
        """Отправляет клавишу в PTY. True, если клавиша поглощена.

        Событие приходит всегда (глобальный обработчик Flet), в том числе
        когда фокус в скрытом поле ввода. Печатаемые символы при этом уже
        уходят из IME поля, поэтому здесь они игнорируются — иначе каждый
        символ дублировался бы. Без фокуса поле молчит, и символы берёт на
        себя диспетчер клавиш (латиница, US-раскладка).
        """
        if self._is_paste_shortcut(event):
            self.paste()
            return True
        if self._is_copy_shortcut(event):
            self.copy()
            return True
        focused = self._input_focused()
        if focused and self._belongs_to_text_field(event):
            return False
        # If not focused and the key is a printable character (US layout), send it directly.
        if not focused and len(event.key) == 1 and not (event.ctrl or event.alt or event.meta):
            self._bridge.write(event.key.encode("utf-8", errors="ignore"))
            self.focus_input()
            return True
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
        if not focused or event.key == "Tab":
            # Tab уводит фокус из поля, а без фокуса кириллицу печатать нечем.
            self.focus_input()
        return True

    def _input_focused(self) -> bool:
        """True, когда скрытое поле ввода смонтировано и держит фокус."""
        return self._view.input_ready and self._view.input_focused

    def _belongs_to_text_field(self, event: ft.KeyboardEvent) -> bool:
        """True, если ввод придёт из скрытого поля, а не из KeyboardEvent.

        Кроме печатаемых символов сюда попадают штатные «вставочные»
        комбинации самого поля: `Ctrl+V` и `Shift+Insert`. Иначе `Ctrl+V`
        ушёл бы в PTY как `0x16`, да ещё и вставился через IME — двойной ввод.
        """
        modified = event.ctrl or event.meta
        if event.key.upper() == "V" and modified and not event.shift:
            return True
        if event.key == "Insert" and event.shift:
            return True
        if modified:
            return False
        # Enter приходит в on_submit, пробел и остальные печатаемые символы —
        # в значение поля; остальное (Backspace, стрелки, Tab, Escape, F-клавиши)
        # обрабатывает диспетчер.
        return event.key in self.TEXT_FIELD_KEYS or len(event.key) == 1

    def _is_paste_shortcut(self, event: ft.KeyboardEvent) -> bool:
        """Вставка, которую сессия берёт на себя.

        `Ctrl+V` и `Shift+Insert` при сфокусированном поле обрабатывает само
        поле, иначе вставка случилась бы дважды. Без фокуса и всегда для
        `Ctrl+Shift+V` читаем буфер через `ft.Clipboard`.
        """
        if not (event.ctrl or event.meta or event.shift):
            return False
        focused = self._input_focused()
        if event.key == "Insert":
            return event.shift and not focused
        if event.key.upper() != "V" or not (event.ctrl or event.meta):
            return False
        return event.shift or not focused

    def _is_copy_shortcut(self, event: ft.KeyboardEvent) -> bool:
        """Копирование в буфер: `Ctrl+Shift+C` и `Ctrl+Insert`.

        Обычный `Ctrl+C` намеренно не перехватывается: это SIGINT для шелла.
        """
        if not (event.ctrl or event.meta):
            return False
        if event.key == "Insert":
            return True
        return event.shift and event.key.upper() == "C"

    # --- Буфер обмена ---

    def copy_text(self) -> str:
        """Что попадает в буфер обмена: видимая область экрана без пустых полей."""
        return self._screen.visible_text()

    def copy(self) -> None:
        """Кладёт видимую область терминала в системный буфер обмена."""
        if self._page is None:
            logger.warning(
                "TerminalSession %s: no page for clipboard copy", self.session_id
            )
            return
        text = self.copy_text()
        if not text:
            return
        try:
            self._page.run_task(self._copy_to_clipboard, text)
        except (AttributeError, RuntimeError):
            logger.warning(
                "TerminalSession %s: clipboard copy is not available", self.session_id
            )

    async def _copy_to_clipboard(self, text: str) -> None:
        try:
            if self._clipboard is None:
                self._clipboard = ft.Clipboard()
            await self._clipboard.set(text)
        except Exception:  # noqa: BLE001 — сервис буфера есть не на всех платформах
            logger.warning(
                "TerminalSession %s: clipboard is not writable", self.session_id
            )
            return
        logger.info("TerminalSession %s: copied %d chars", self.session_id, len(text))

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
