# ghostty_wrapper/core/terminal/ghostty/platform/linux_test.py
"""Тесты Linux-реализации Ghostty (без реального ghostty)."""
from __future__ import annotations

from core.terminal.ghostty.platform import linux as l


def test_extra_args_cwd() -> None:
    """cwd добавляет --working-directory=."""
    assert l._extra_args(None, "/tmp") == ["--working-directory=/tmp"]


def test_extra_args_command() -> None:
    """command добавляет -e."""
    assert l._extra_args("echo hi", None) == ["-e", "echo hi"]


def test_extra_args_both() -> None:
    """cwd и command передаются вместе."""
    assert l._extra_args("echo hi", "/tmp") == [
        "--working-directory=/tmp",
        "-e",
        "echo hi",
    ]