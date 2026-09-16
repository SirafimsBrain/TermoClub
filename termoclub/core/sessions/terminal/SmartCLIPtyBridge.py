# termoclub/core/sessions/terminal/SmartCLIPtyBridge.py
"""Асинхронный мост к псевдотерминалу через smartcli-toolkit.

Заменяет `PtyBridge` там, где нужен стек smartcli: PTY владеет
`smartcli_core.PtySession` (кросс-платформенный backend — `pty`/`fork` на
POSIX, `pywinpty` на Windows), а не наш собственный `pty.fork()`.

Публичный интерфейс совпадает с `PtyBridge` — `start`/`pump`/`write`/
`resize`/`request_stop`/`terminate` плюс `running`, — поэтому
`TerminalSession` работает с обоими мостами без развилок.

Отличия реализации:

* `PtySession.pump()` — синхронное неблокирующее чтение: возвращает то, что
  уже пришло, и `b""`, если данных нет. Поэтому pump-цикл читает без паузы,
  пока данные есть, и ждёт `POLL_INTERVAL`, когда их нет; между итерациями с
  данными он отдаёт управление `await asyncio.sleep(0)` (иначе непрерывный
  вывод не давал бы циклу ни отрисовать экран, ни принять ввод).
* `PtySession.pump()` сам скармливает байты своей `ScreenModel` и отвечает
  на DSR/DA-запросы программы (`ESC[6n` / `ESC[c`). Экран отрисовки берёт
  готовую модель через `.model` и не кормит её повторно — см.
  `SmartCLIScreen`.
* `PtySession.close()` на интерактивном шелле блокирует около секунды:
  `PosixPtyBackend` шлёт SIGTERM (интерактивный `bash` его игнорирует),
  ждёт ~1 с и только потом шлёт SIGKILL. `terminate()` вызывается
  синхронно из UI-потока при закрытии вкладки, поэтому гашение уходит в
  фоновый поток — вкладка исчезает сразу.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
import threading

logger = logging.getLogger(__name__)

try:  # пакет smartcli-toolkit ставит модуль smartcli_core
    from smartcli_core import PtySession
except ImportError:  # pragma: no cover — зависит от окружения
    PtySession = None  # type: ignore[assignment]

#: Текст ошибки, когда пакет не установлен (показывается при открытии вкладки).
MISSING_PACKAGE = (
    "smartcli-toolkit не установлен: терминал smartcli недоступен. "
    "Установите пакет (`pip install smartcli-toolkit`) и перезапустите приложение."
)


class SmartCLIPtyBridge:
    """Владеет PTY-процессом через `smartcli_core.PtySession`."""

    #: Пауза опроса, когда данных нет (сек).
    POLL_INTERVAL = 0.01

    def __init__(
        self,
        shell: str | None = None,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        cols: int = 80,
        rows: int = 24,
    ) -> None:
        if PtySession is None:
            raise RuntimeError(MISSING_PACKAGE)
        self._shell = shell or os.environ.get("SHELL") or "/bin/bash"
        self._args = list(args or [])
        self._cwd = cwd
        self._env = env
        self._cols = cols
        self._rows = rows
        # `PtySession` создаётся сразу, а не в start(): модель экрана нужна уже
        # при сборке сессии — её оборачивает `SmartCLIScreen`. Конструктор
        # smartcli лишь выбирает backend и создаёт сетку, платформенные API
        # не трогает, поэтому это безопасно и до запуска шелла.
        self._session = PtySession(cols=cols, rows=rows)
        self._stop = asyncio.Event()
        self._started = False

    @property
    def model(self):  # noqa: ANN201 — smartcli_core.ScreenModel
        """Живая `ScreenModel` smartcli (в неё пишет `PtySession.pump()`).

        Ссылка на сессию живёт всё время существования моста, поэтому после
        `terminate()` сетка остаётся читаемой — она нужна экрану отрисовки.
        """
        return self._session.model

    @property
    def running(self) -> bool:
        """True, пока PTY-процесс запущен и мост не остановлен."""
        return self._started and not self._stop.is_set()

    def _spawn_target(self) -> str | list[str]:
        """Команда для PTY: прямой `exec`, а при `cwd`/`env` — через `sh -c`.

        `PtySession.start()` принимает либо строку (запускается как
        `/bin/sh -c "<строка>"`), либо последовательность (прямой `execvp`).
        Смена каталога и переменные окружения в backend не предусмотрены,
        поэтому при них команда собирается строкой для `sh` — с
        экранированием всех подставляемых значений.
        """
        argv = [self._shell, *self._args]
        if self._cwd is None and not self._env:
            return argv
        steps: list[str] = []
        if self._cwd is not None:
            steps.append(f"cd {shlex.quote(self._cwd)}")
        if self._env:
            assignments = " ".join(
                f"{key}={shlex.quote(value)}" for key, value in self._env.items()
            )
            steps.append(f"exec env {assignments} {shlex.join(argv)}")
        else:
            steps.append(f"exec {shlex.join(argv)}")
        return " && ".join(steps)

    async def start(self) -> None:
        """Форкает PTY и запускает шелл."""
        if self._started:
            return
        # `PtySession.start()` синхронный: fork+exec достаточно быстр, чтобы
        # не выносить его в поток (в отличие от блокирующего чтения).
        self._session.start(self._spawn_target())
        self._started = True
        logger.info("SmartCLIPtyBridge: spawned %s", self._shell)

    def write(self, data: bytes) -> None:
        """Пишет байты в stdin PTY (ввод пользователя)."""
        if not self._started or self._stop.is_set():
            return
        try:
            # `send_text()` кодирует обратно в UTF-8. Круговорот точный:
            # управляющие байты ввода (CR, 0x7f, ESC-последовательности) —
            # ASCII, а печатаемый текст приходит из TextInputBridge уже в UTF-8.
            self._session.send_text(data.decode("utf-8"))
        except (OSError, ValueError, RuntimeError):
            logger.warning("SmartCLIPtyBridge: write failed, pty closed")

    async def pump(self, on_data) -> None:  # noqa: ANN001 — Callable[[bytes], None]
        """Читает PTY до остановки; чанки отдаёт в `on_data(bytes)`."""
        session = self._session
        if session is None:
            return
        while not self._stop.is_set():
            try:
                chunk = session.pump()
            except (OSError, ValueError):
                break  # fd закрыт (terminate) или ребёнок завершился
            if chunk:
                on_data(chunk)
                # Данных может быть ещё — читаем без паузы, но обязательно
                # отдаём управление циклу: у `PtySession.pump()` чтение
                # неблокирующее, и на непрерывном выводе (`yes`, `cat` большого
                # файла) этот `continue` крутился бы бесконечно, не давая
                # исполниться ни отрисовке, ни вводу, ни закрытию вкладки.
                # `sleep(0)` не задерживает: ожидание остаётся только в ветке
                # «данных нет» ниже.
                await asyncio.sleep(0)
                continue
            if not session.is_alive():
                break
            await asyncio.sleep(self.POLL_INTERVAL)
        logger.info("SmartCLIPtyBridge: pump finished")

    def resize(self, cols: int, rows: int) -> None:
        """Меняет размер окна PTY и модели экрана (шелл получит SIGWINCH)."""
        self._cols = cols
        self._rows = rows
        if self._started:
            try:
                self._session.resize(cols, rows)
            except (OSError, ValueError):
                return
        logger.info("SmartCLIPtyBridge: resized to %dx%d", cols, rows)

    def request_stop(self) -> None:
        """Просит pump-цикл остановиться (мягко)."""
        self._stop.set()

    def terminate(self) -> None:
        """Гасит PTY-процесс, не морозя UI-поток.

        `PtySession.close()` на интерактивном шелле занимает ~1 с (SIGTERM
        `bash` игнорирует, backend ждёт его секунду и только затем шлёт
        SIGKILL). Закрытие вкладки синхронно, поэтому гашение уходит в
        отдельный поток: вкладка исчезает сразу, шелл умирает следом.
        """
        self._stop.set()
        self._started = False
        # Ссылку на сессию не теряем: сетку читает экран отрисовки, а гашение
        # идёт в фоновом потоке.
        threading.Thread(
            target=self._close_quietly,
            args=(self._session,),
            name="smartcli-pty-close",
            daemon=True,
        ).start()
        logger.info("SmartCLIPtyBridge: terminated")

    @staticmethod
    def _close_quietly(session) -> None:  # noqa: ANN001 — smartcli_core.PtySession
        """Закрывает PTY-сессию в фоне: teardown не должен ничего ронять."""
        try:
            session.close()
        except Exception:  # noqa: BLE001 — фон: любая ошибка только в лог
            logger.warning("SmartCLIPtyBridge: background close failed", exc_info=True)
