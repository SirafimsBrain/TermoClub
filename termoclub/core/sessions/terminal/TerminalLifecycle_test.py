# termoclub/core/sessions/terminal/TerminalLifecycle_test.py
"""Сквозной lifecycle pyte-вкладки на живом event loop (без GUI)."""
from __future__ import annotations

import asyncio
import os

import pytest

from core.sessions.SessionStatus import SessionStatus
from core.sessions.terminal.TerminalSession import TerminalSession


class _LivePage:
    """Минимальный page: run_task реально планирует задачи в loop."""

    def run_task(self, handler, *args):  # type: ignore[no-untyped-def]
        return asyncio.ensure_future(handler(*args))


def test_shell_exit_closes_session() -> None:
    """Шелл с instant-exit: pump видит EOF, вкладка самозакрывается."""
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        terminated: list[str] = []
        session = TerminalSession(
            shell="/bin/bash",
            args=["-c", "exit 0"],
            on_terminated=terminated.append,
        )
        session.get_content()
        session.start(_LivePage())  # type: ignore[arg-type]
        assert session.status == SessionStatus.RUNNING
        await asyncio.wait_for(_wait_closed(session), timeout=10)
        assert session.status == SessionStatus.CLOSED
        # Уведомление приходит следующим тиком цикла (см. `_notify_terminated`).
        await asyncio.wait_for(_wait_terminated(terminated), timeout=10)
        assert terminated == [session.session_id]
        session.cleanup()  # повторный cleanup после смерти — безопасен

    asyncio.run(scenario())


async def _wait_closed(session: TerminalSession) -> None:
    while session.status != SessionStatus.CLOSED:
        await asyncio.sleep(0.02)


async def _wait_terminated(terminated: list[str]) -> None:
    while not terminated:
        await asyncio.sleep(0.02)


def test_pty_output_renders_to_display() -> None:
    """Вывод PTY реально рендерится в текст экрана."""
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        session = TerminalSession(shell="/bin/cat", args=[])
        session.get_content()
        session.start(_LivePage())  # type: ignore[arg-type]
        await asyncio.wait_for(_wait_running(session), timeout=10)
        session._bridge.write(b"hello-pty\n")
        await asyncio.wait_for(_wait_text(session, "hello-pty"), timeout=10)
        session.cleanup()
        assert session.status == SessionStatus.CLOSED

    asyncio.run(scenario())


async def _wait_running(session: TerminalSession) -> None:
    while not session._bridge.running:
        await asyncio.sleep(0.02)


async def _wait_text(session: TerminalSession, needle: str) -> None:
    while needle not in session.display_text:
        await asyncio.sleep(0.02)
