# termoclub/core/sessions/terminal/SmartCLIPtyBridge_test.py
"""Тесты моста к smartcli-core: команда запуска, ввод-вывод, гашение."""
from __future__ import annotations

import asyncio
import os
import shutil
import threading

import pytest

from core.sessions.terminal.SmartCLIPtyBridge import SmartCLIPtyBridge


def test_direct_exec_without_cwd_or_env() -> None:
    """Без cwd/env шелл запускается напрямую, без лишнего `sh`."""
    bridge = SmartCLIPtyBridge(shell="/bin/bash", args=["-l"])
    assert bridge._spawn_target() == ["/bin/bash", "-l"]


def test_cwd_and_env_go_through_shell_with_quoting() -> None:
    """cwd и окружение подставляются в `sh -c` с экранированием значений."""
    bridge = SmartCLIPtyBridge(
        shell="/bin/bash", args=["-l"], cwd="/tmp/my dir", env={"FOO": "a b"}
    )
    target = bridge._spawn_target()
    assert isinstance(target, str)
    assert target == "cd '/tmp/my dir' && exec env FOO='a b' /bin/bash -l"


def test_cwd_without_env() -> None:
    """Только cwd: команда всё равно собирается строкой для `sh`."""
    bridge = SmartCLIPtyBridge(shell="/bin/bash", cwd="/tmp")
    assert bridge._spawn_target() == "cd /tmp && exec /bin/bash"


def test_shell_falls_back_to_bash_without_env_shell() -> None:
    """Пустой SHELL в окружении не оставляет терминал без программы."""
    bridge = SmartCLIPtyBridge(shell=None)
    assert bridge._shell


def test_model_is_available_before_start() -> None:
    """Модель экрана есть уже в конструкторе: её оборачивает SmartCLIScreen."""
    bridge = SmartCLIPtyBridge(shell="/bin/cat", cols=90, rows=33)
    assert (bridge.model.cols, bridge.model.rows) == (90, 33)


def test_missing_package_raises_a_clear_error(monkeypatch) -> None:
    """Без smartcli-toolkit конструктор объясняет, что установить."""
    from core.sessions.terminal import SmartCLIPtyBridge as module

    monkeypatch.setattr(module, "PtySession", None)
    with pytest.raises(RuntimeError, match="smartcli-toolkit"):
        SmartCLIPtyBridge()


def test_write_before_start_is_ignored() -> None:
    """Запись до start() не падает."""
    SmartCLIPtyBridge(shell="/bin/cat").write(b"x")


def test_terminate_without_start_is_safe() -> None:
    """terminate() до start() безопасен и снимает running."""
    bridge = SmartCLIPtyBridge(shell="/bin/cat")
    bridge.terminate()
    assert not bridge.running


def test_pty_echo_roundtrip_feeds_the_screen_model() -> None:
    """Байты из PTY (cat) проходят pump и оказываются в модели экрана."""
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        bridge = SmartCLIPtyBridge(shell="/bin/cat", args=[])
        await bridge.start()
        assert bridge.running
        model = bridge.model
        pump = asyncio.ensure_future(bridge.pump(lambda _chunk: None))
        bridge.write("привет".encode("utf-8"))
        await asyncio.wait_for(_wait_text(model, "привет"), timeout=5)
        bridge.request_stop()
        bridge.terminate()
        await asyncio.wait_for(pump, timeout=5)
        assert not bridge.running
        assert "привет" in model.text()

    asyncio.run(scenario())


async def _wait_text(model, needle: str) -> None:  # noqa: ANN001
    while needle not in model.text():
        await asyncio.sleep(0.01)


def test_resize_keeps_pty_and_model_in_sync() -> None:
    """resize() меняет и окно PTY, и сетку модели (иначе они разъезжаются)."""
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        bridge = SmartCLIPtyBridge(shell="/bin/cat", args=[])
        await bridge.start()
        model = bridge.model
        bridge.resize(100, 30)
        assert (model.cols, model.rows) == (100, 30)
        bridge.terminate()

    asyncio.run(scenario())


def test_flooding_output_does_not_starve_the_event_loop() -> None:
    """Непрерывный вывод не занимает цикл целиком.

    `PtySession.pump()` читает неблокирующе, поэтому ветка «данные есть»
    крутилась бы без `await`: на `yes` замирали и отрисовка, и ввод, и
    закрытие вкладки (тикер в том же цикле не получал управления).

    Сценарий идёт в отдельном потоке с таймаутом: на голодном цикле не
    сработает даже таймаут `wait_for`, и тест повис бы навсегда — вместо
    этого получаем внятное падение.
    """
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")
    producer = shutil.which("yes")
    if producer is None:
        pytest.skip("`yes` is not available")

    thread = threading.Thread(
        target=lambda: asyncio.run(_flood(producer)), daemon=True
    )
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive(), "pump() занимает цикл целиком: тикер не идёт"


async def _flood(producer: str) -> None:
    """Льёт непрерывный вывод и считает тики соседней задачи."""
    bridge = SmartCLIPtyBridge(shell=producer, args=[])
    await bridge.start()
    first_chunk = asyncio.Event()

    def on_data(_chunk: bytes) -> None:
        first_chunk.set()

    pump = asyncio.ensure_future(bridge.pump(on_data))
    # Ждём начала потока: иначе первый тик успевает пройти на тишине
    # (шелл стартует не мгновенно) и тест перестал бы ловить голодание.
    await asyncio.wait_for(first_chunk.wait(), timeout=5)

    ticks = 0
    stop = asyncio.Event()

    async def ticker() -> None:
        nonlocal ticks
        while not stop.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    ticker_task = asyncio.ensure_future(ticker())
    await asyncio.sleep(0.6)
    stop.set()
    bridge.request_stop()
    bridge.terminate()
    await asyncio.wait_for(pump, timeout=5)
    await ticker_task
    # На голодном цикле тикер не успел бы ни разу. Тиков немного и с
    # исправлением: разбор одной порции вывода занимает десятки
    # миллисекунд, так что счётчик здесь — только про живость цикла.
    assert ticks >= 2


def test_shell_exit_ends_the_pump_loop() -> None:
    """Самозавершение шелла останавливает pump без request_stop()."""
    if os.name == "nt":
        pytest.skip("PTY is not supported on Windows")

    async def scenario() -> None:
        bridge = SmartCLIPtyBridge(shell="/bin/bash", args=["-c", "exit 0"])
        await bridge.start()
        # wait_for бросит TimeoutError, если pump не заметит смерть шелла.
        await asyncio.wait_for(bridge.pump(lambda _chunk: None), timeout=5)
        assert not bridge._session.is_alive()
        bridge.terminate()

    asyncio.run(scenario())
