# termoclub/core/terminal/ghostty/platform/macos_test.py
"""Тесты AppleScript-сборки macOS (без реального osascript)."""
from __future__ import annotations

from core.terminal.ghostty.platform import macos as m


def test_window_script_has_new_window() -> None:
    """Скрипт окна содержит new window."""
    assert "new window" in m._window_script(None, None)


def test_window_script_with_command() -> None:
    """Скрипт окна с командой содержит set command of cfg."""
    script = m._window_script("echo hi", None)
    assert 'set command of cfg to "echo hi"' in script


def test_tab_script_new_tab_front_window() -> None:
    """Скрипт вкладки создаёт tab в переднем окне."""
    script = m._tab_script(None, None)
    assert "set win to front window" in script
    assert "new tab in win" in script


def test_cfg_script_cwd() -> None:
    """cwd задаёт initial working directory."""
    script = m._cfg_script(None, "/tmp")
    assert 'set initial working directory of cfg to "/tmp"' in script


def test_as_string_escapes_quotes() -> None:
    """Двойные кавычки в AppleScript-строке удваиваются."""
    assert m._as_string('a"b') == '"a""b"'