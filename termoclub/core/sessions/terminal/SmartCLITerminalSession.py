# termoclub/core/sessions/terminal/SmartCLITerminalSession.py
"""Сессия внутреннего терминала на smartcli-toolkit (заменяет flet-terminal).

Это `TerminalSession` с другим движком: PTY и эмуляция экрана берутся из
`smartcli_core`, а ввод, буфер обмена, троттлинг отрисовки, фокус и разметка
наследуются без единой копии кода. Стык обеспечивают два адаптера:

* `SmartCLIPtyBridge` повторяет интерфейс `PtyBridge`
  (`start`/`pump`/`write`/`resize`/`request_stop`/`terminate`);
* `SmartCLIScreen` повторяет интерфейс `PyteScreen`, которым пользуется
  `TerminalView` (сетка, курсор, размер, видимый текст).

Поэтому `TerminalView` рисует оба терминала одинаково, и каналы ввода
(кириллица через IME-поле, служебные клавиши через диспетчер, вставка и
копирование) работают в них идентично.

Сессия намеренно ничего не добавляет на `page`: контрол отдаётся только из
`get_content()`, а монтирует его `WorkspaceStage`. `page.add()` создавал бы
в окне вторую панель рядом с `ApplicationLayout` — терминал попадал в
корень страницы, а не в рабочую область.
"""
from __future__ import annotations

from core.sessions.terminal.SmartCLIPtyBridge import SmartCLIPtyBridge
from core.sessions.terminal.SmartCLIScreen import SmartCLIScreen
from core.sessions.terminal.TerminalSession import TerminalSession


class SmartCLITerminalSession(TerminalSession):
    """Вкладка внутреннего терминала на smartcli-toolkit (kind `terminal-gpu`)."""

    KIND = "terminal-gpu"

    @property
    def icon(self) -> str:
        """Имя иконки Font Awesome для вкладки/карточки."""
        return "terminal"

    # --- Движок: smartcli вместо собственных PtyBridge/PyteScreen ---

    def _create_bridge(
        self,
        shell: str | None,
        args: list[str] | None,
        cwd: str | None,
        cols: int,
        rows: int,
    ) -> SmartCLIPtyBridge:
        """PTY на smartcli-core: кроссплатформенный backend вместо `pty.fork()`."""
        return SmartCLIPtyBridge(shell=shell, args=args, cwd=cwd, cols=cols, rows=rows)

    def _create_screen(self, columns: int, lines: int) -> SmartCLIScreen:
        """Экран-адаптер над `ScreenModel`, которой владеет мост.

        Размер модели задан при создании моста, поэтому аргументы не нужны:
        сигнатура сохранена для совместимости с базовым классом.
        """
        return SmartCLIScreen(self._bridge.model)
