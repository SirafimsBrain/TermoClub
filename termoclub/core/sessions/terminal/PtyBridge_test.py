# termoclub/core/sessions/terminal/PtyBridge_test.py
"""Тесты PTY-моста (Linux/macOS)."""
from __future__ import annotations

import asyncio
import os

import pytest

from core.sessions.terminal.PtyBridge import PtyBridge


def test_pty_echo_roundtrip() -> None:
    """Байт, записанный в PTY с cat, возвращается через pump."""
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        bridge = PtyBridge(shell="/bin/cat", args=[])
        await bridge.start()
        assert bridge.running
        received: list[bytes] = []
        pump = asyncio.ensure_future(bridge.pump(received.append))
        bridge.write(b"ping\n")
        await asyncio.wait_for(_wait_for(received), timeout=5)
        bridge.request_stop()
        bridge.terminate()
        await pump
        assert not bridge.running
        assert b"ping" in b"".join(received)

    asyncio.run(scenario())


async def _wait_for(received: list[bytes]) -> None:
    while not received:
        await asyncio.sleep(0.01)


def test_start_on_unsupported_platform_raises(monkeypatch) -> None:
    """На платформе без PTY — понятный OSError."""
    monkeypatch.setattr(os, "name", "nt")
    bridge = PtyBridge(shell="/bin/cat")

    async def scenario() -> None:
        with pytest.raises(OSError):
            await bridge.start()

    asyncio.run(scenario())


def test_write_before_start_is_ignored() -> None:
    """Запись до start() не падает."""
    PtyBridge(shell="/bin/cat").write(b"x")


def test_terminate_without_start_is_safe() -> None:
    """terminate() до start() безопасен."""
    bridge = PtyBridge(shell="/bin/cat")
    bridge.terminate()
    assert not bridge.running
