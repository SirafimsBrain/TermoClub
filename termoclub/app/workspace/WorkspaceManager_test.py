# termoclub/app/workspace/WorkspaceManager_test.py
"""Тесты менеджера сессий (без страницы)."""
from __future__ import annotations

import flet as ft

from app.workspace.WorkspaceManager import WorkspaceManager
from core.sessions.SessionFactory import SessionFactory
from core.sessions.SessionStatus import SessionStatus
from core.sessions.WorkspaceItem import WorkspaceItem


class StubItem(WorkspaceItem):
    KIND = "stub"

    def __init__(self, title: str = "stub", session_id: str | None = None) -> None:
        super().__init__(title, session_id)
        self.cleaned = False

    def start(self, page) -> None:  # type: ignore[no-untyped-def]
        self._status = SessionStatus.RUNNING

    def get_content(self) -> ft.Control:
        return ft.Text(self.title)

    def cleanup(self) -> None:
        self.cleaned = True
        self._status = SessionStatus.CLOSED


def _manager_with(n: int) -> tuple[WorkspaceManager, list[StubItem]]:
    SessionFactory.register("stub", lambda **kwargs: StubItem(**kwargs))
    manager = WorkspaceManager()
    items = [manager.open("stub", page=object(), title=f"s{i}") for i in range(n)]
    return manager, items


def test_open_activates_and_notifies() -> None:
    """open() создаёт, активирует и уведомляет подписчиков."""
    manager = WorkspaceManager()
    SessionFactory.register("stub", lambda **kwargs: StubItem(**kwargs))
    calls: list[bool] = []
    manager.subscribe(lambda: calls.append(True))
    item = manager.open("stub", title="a")
    assert manager.get_active() is item
    assert calls, "listeners must be notified"


def test_close_repairs_active() -> None:
    """Закрытие активной передаёт фокус соседу."""
    manager, items = _manager_with(2)
    manager.close(items[1].session_id)
    assert items[1].cleaned
    assert manager.get_active() is items[0]
    assert manager.get(items[1].session_id) is None


def test_activate_blurs_previous() -> None:
    """Активация снимает фокус с предыдущей сессии."""
    manager, items = _manager_with(2)
    manager.activate(items[0].session_id)
    assert items[0].status == SessionStatus.FOCUSED
    assert items[1].status == SessionStatus.RUNNING


def test_move_reorders() -> None:
    """move() меняет порядок сессий."""
    manager, items = _manager_with(3)
    manager.move(items[0].session_id, 2)
    assert [i.session_id for i in manager.sessions] == [
        items[1].session_id,
        items[2].session_id,
        items[0].session_id,
    ]


def test_terminated_item_is_closed() -> None:
    """Самозавершение убирает сессию."""
    manager, items = _manager_with(1)
    manager._on_item_terminated(items[0].session_id)
    assert manager.sessions == []
    assert manager.active_id is None


def test_cap_closes_oldest_inactive() -> None:
    """Сверх лимита закрываются старейшие неактивные."""
    manager = WorkspaceManager()
    manager.MAX_SESSIONS = 2
    SessionFactory.register("stub", lambda **kwargs: StubItem(**kwargs))
    first = manager.open("stub", title="first")
    manager.open("stub", title="second")
    assert not first.cleaned
    assert len(manager.sessions) == 2
