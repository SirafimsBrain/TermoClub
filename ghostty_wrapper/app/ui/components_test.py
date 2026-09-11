# ghostty_wrapper/app/ui/components_test.py
"""Тесты единого формата результата."""
from __future__ import annotations

from core.result import Result


def test_result_success() -> None:
    """Успешный Result имеет ok=True."""
    r = Result.success("done")
    assert r.ok is True
    assert r.message == "done"


def test_result_failure() -> None:
    """Ошибочный Result имеет ok=False и сообщение."""
    r = Result.failure("boom")
    assert r.ok is False
    assert r.message == "boom"