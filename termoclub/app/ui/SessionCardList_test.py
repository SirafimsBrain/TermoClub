# termoclub/app/ui/SessionCardList_test.py
"""Тесты списка карточек с перетаскиванием."""
from __future__ import annotations

import flet as ft

from app.ui.SessionCardData import SessionCardData
from app.ui.SessionCardList import SessionCardList
from core.sessions.SessionStatus import SessionStatus


def _data(sid: str) -> SessionCardData:
    return SessionCardData(
        session_id=sid,
        title=sid,
        kind="terminal",
        source="workspace",
        status=SessionStatus.RUNNING,
        icon="terminal",
    )


def test_sync_adds_and_removes_rows() -> None:
    """sync() сверяет строки с сессиями."""
    cards = SessionCardList()
    cards.build()
    cards.sync([_data("a"), _data("b")])
    assert len(cards._list.controls) == 2
    assert cards._count.value == "2"
    cards.sync([_data("a")])
    assert len(cards._list.controls) == 1
    assert cards._count.value == "1"


def test_rows_have_drag_handles() -> None:
    """Каждая строка начинается с ручки перетаскивания."""
    cards = SessionCardList()
    cards.build()
    cards.sync([_data("a")])
    row = cards._list.controls[0]
    assert isinstance(row, ft.Container)
    inner = row.content
    assert isinstance(inner, ft.Row)
    assert isinstance(inner.controls[0], ft.ReorderableDragHandle)


def test_reorder_forwards_flutter_corrected_index() -> None:
    """on_reorder получает индекс после извлечения (old<new: -1)."""
    calls: list[tuple[int, int]] = []
    cards = SessionCardList(on_reorder=lambda o, n: calls.append((o, n)))

    class _Event:
        old_index = 0
        new_index = 2

    cards._handle_reorder(_Event())
    assert calls == [(0, 1)]
