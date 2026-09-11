# termoclub/core/sessions/terminal/PtyBridge.py
"""Асинхронный мост к псевдотерминалу (PTY) локального шелла."""
from __future__ import annotations

import asyncio
import logging
import os
import signal

logger = logging.getLogger(__name__)

try:
    import pty
except ImportError:  # Windows: модуля pty нет
    pty = None  # type: ignore[assignment]


class PtyBridge:
    """Владеет PTY-процессом: запуск, запись, чтение, завершение.

    Чтение — через `run_in_executor`, поэтому pump не блокирует UI-цикл.
    Поддерживаются Linux/macOS; на других платформах `start()` бросает
    `OSError` с понятным текстом.
    """

    def __init__(
        self,
        shell: str | None = None,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        cols: int = 80,
        rows: int = 24,
    ) -> None:
        self._shell = shell or os.environ.get("SHELL", "/bin/bash")
        self._args = args or []
        self._cwd = cwd
        self._env = env
        self._cols = cols
        self._rows = rows
        self._master_fd: int | None = None
        self._child_pid: int | None = None
        self._stop = asyncio.Event()
        self._started = False

    @property
    def running(self) -> bool:
        """True, пока PTY-процесс запущен и мост не остановлен."""
        return self._started and not self._stop.is_set()

    async def start(self) -> None:
        """Форкает PTY и запускает шелл (только Linux/macOS)."""
        if os.name == "nt" or pty is None:
            raise OSError("PTY sessions are not supported on this platform")
        pid, fd = pty.fork()
        if pid == 0:  # дочерний процесс
            try:
                if self._cwd:
                    os.chdir(self._cwd)
                self._set_winsize(1)
                environ = dict(os.environ)
                if self._env:
                    environ.update(self._env)
                os.execvpe(self._shell, [self._shell, *self._args], environ)
            finally:
                os._exit(1)
        self._child_pid = pid
        self._master_fd = fd
        self._started = True
        logger.info("PtyBridge: spawned %s (pid=%s)", self._shell, pid)

    def write(self, data: bytes) -> None:
        """Пишет байты в stdin PTY (ввод пользователя)."""
        if self._master_fd is None or self._stop.is_set():
            return
        try:
            os.write(self._master_fd, data)
        except OSError:
            logger.warning("PtyBridge: write failed, master fd closed")

    async def pump(self, on_data) -> None:
        """Читает PTY до остановки; чанки отдаёт в `on_data(bytes)`."""
        assert self._master_fd is not None, "PtyBridge.start() was not called"
        loop = asyncio.get_running_loop()
        fd = self._master_fd
        while not self._stop.is_set():
            try:
                chunk = await loop.run_in_executor(None, os.read, fd, 65536)
            except OSError:
                break
            if not chunk:  # EOF: дочерний процесс завершился
                break
            on_data(chunk)
        logger.info("PtyBridge: pump finished (pid=%s)", self._child_pid)

    def resize(self, cols: int, rows: int) -> None:
        """Меняет размер окна PTY (шелл получает SIGWINCH)."""
        self._cols = cols
        self._rows = rows
        if self._master_fd is not None:
            self._set_winsize(self._master_fd)
        logger.info("PtyBridge: resized to %dx%d", cols, rows)

    def request_stop(self) -> None:
        """Просит pump-цикл остановиться (мягко)."""
        self._stop.set()

    def terminate(self) -> None:
        """Убивает дочерний процесс и закрывает PTY (синхронно)."""
        self._stop.set()
        if self._child_pid is not None:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
            try:
                os.waitpid(self._child_pid, os.WNOHANG)
            except (OSError, ChildProcessError):
                pass
            self._child_pid = None
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        self._started = False
        logger.info("PtyBridge: terminated")

    def _set_winsize(self, fd: int) -> None:
        try:
            import fcntl
            import struct
            import termios

            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", self._rows, self._cols, 0, 0))
        except (ImportError, OSError):
            pass
