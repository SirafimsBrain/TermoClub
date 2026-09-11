# termoclub/app/ui/WorkspaceTabs_test.py
"""Тесты панели вкладок и хоста контента."""
from __future__ import annotations

import flet as ft

from app.ui.SessionCardData import SessionCardData
from app.ui.WorkspaceStage import WorkspaceStage
from app.ui.WorkspaceTabBar import WorkspaceTabBar
from core.sessions.SessionStatus import SessionStatus


def _data(sid: str, active: bool = False) -> SessionCardData:
    return SessionCardData(
        session_id=sid,
        title=sid,
        kind="terminal",
        source="workspace",
        status=SessionStatus.RUNNING,
        icon="terminal",
        active=active,
    )


def test_tabbar_clicks_and_new() -> None:
    """Клик по вкладке — выбор, крестик — закрыть, '+' — создать."""
    selected: list[str] = []
    closed: list[str] = []
    created: list[bool] = []
    bar = WorkspaceTabBar(selected.append, closed.append, lambda: created.append(True))
    bar.build()
    bar.refresh([_data("a", active=True), _data("b")])

    tabs = [c for c in bar._row.controls if isinstance(c, ft.Container)]
    assert len(tabs) == 2
    assert tabs[0].on_click is not None
    tabs[1].on_click(None)  # type: ignore[arg-type]
    assert selected == ["b"]

    closes: list = []

    def visit(node: object) -> None:
        if isinstance(node, ft.IconButton) and node.on_click is not None:
            closes.append(node)
        children = getattr(node, "controls", None)
        if isinstance(children, list):
            for child in children:
                visit(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            visit(content)

    visit(bar._row)
    close_btn = next(b for b in closes if b.icon == ft.Icons.CLOSE)
    close_btn.on_click(None)
    assert closed == ["a"]
    plus_btn = next(b for b in closes if b.icon == ft.Icons.ADD)
    plus_btn.on_click(None)
    assert created == [True]


def test_stage_mount_show_remove() -> None:
    """Stage монтирует один раз, переключает visible, убирает закрытые."""
    stage = WorkspaceStage()
    first, second = ft.Text("1"), ft.Text("2")
    stage.mount("a", first, visible=True)
    stage.mount("b", second, visible=False)
    stage.mount("a", first, visible=True)  # повторный mount — no-op
    assert len(stage._stack.controls) == 2
    stage.show("b")
    by_id = {c.content: v for c, v in [(h, h.visible) for h in stage._stack.controls for c in [h.content]]}
    assert by_id[first] is False
    assert by_id[second] is True
    stage.remove("a")
    assert len(stage._stack.controls) == 1
