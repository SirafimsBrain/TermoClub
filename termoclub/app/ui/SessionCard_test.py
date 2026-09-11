# termoclub/app/ui/SessionCard_test.py
"""Тесты карточки сессии и дескриптора."""
from __future__ import annotations

import flet as ft

from app.ui.SessionCard import SessionCard
from app.ui.SessionCardData import SessionCardData
from core.sessions.SessionStatus import SessionStatus
from core.sessions.editor.EditorSession import EditorSession


def _data() -> SessionCardData:
    return SessionCardData(
        session_id="s1",
        title="ops",
        kind="terminal",
        source="workspace",
        status=SessionStatus.RUNNING,
        icon="terminal",
        active=True,
    )


def _texts(control: ft.Control) -> list[str]:
    found: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, ft.Text) and isinstance(node.value, str):
            found.append(node.value)
        for attr in ("controls",):
            children = getattr(node, attr, None)
            if isinstance(children, list):
                for child in children:
                    visit(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            visit(content)

    visit(control)
    return found


def test_from_item_maps_session() -> None:
    """Дескриптор строится из сессии без связей с UI."""
    item = EditorSession(title="readme")
    data = SessionCardData.from_item(item, active=True)
    assert data.session_id == item.session_id
    assert data.title == "readme"
    assert data.kind == "editor"
    assert data.source == "workspace"
    assert data.icon == "file-lines"
    assert data.active is True


def test_card_shows_title_kind_status() -> None:
    """Карточка отображает заголовок, вид и статус."""
    labels = _texts(SessionCard(_data()).build())
    assert "ops" in labels
    assert "workspace · terminal" in labels
    assert "running" in labels


def test_card_click_selects_and_close_closes() -> None:
    """Клик по карточке — фокус, крестик — закрыть."""
    selected: list[str] = []
    closed: list[str] = []
    card = SessionCard(_data(), selected.append, closed.append).build()
    assert isinstance(card, ft.Container)
    assert card.on_click is not None
    card.on_click(None)  # type: ignore[arg-type]
    assert selected == ["s1"]

    closes: list = []

    def visit(node: object) -> None:
        if isinstance(node, ft.IconButton) and node.on_click is not None:
            closes.append(node.on_click)
        children = getattr(node, "controls", None)
        if isinstance(children, list):
            for child in children:
                visit(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            visit(content)

    visit(card)
    assert closes, "card must have a close button"
    closes[0](None)
    assert closed == ["s1"]
