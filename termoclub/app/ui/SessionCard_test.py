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


def _text_controls(control: ft.Control) -> list[ft.Text]:
    """Все `ft.Text` в дереве контрола."""
    found: list[ft.Text] = []

    def visit(node: object) -> None:
        if isinstance(node, ft.Text):
            found.append(node)
        for child in getattr(node, "controls", None) or []:
            visit(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            visit(content)

    visit(control)
    return found


def test_card_text_never_wraps_into_a_vertical_column() -> None:
    """Заголовок и подпись ограничены одной строкой с многоточием.

    Панель с карточками тянут мышью: без ограничения заголовок в узкой
    карточке переносился по одному символу в строке, и карточка вырастала
    в высокий столбик из букв.
    """
    texts = _text_controls(SessionCard(_data()).build())
    by_value = {text.value: text for text in texts}
    title = by_value["ops"]
    assert title.max_lines == 1
    assert title.overflow == ft.TextOverflow.ELLIPSIS
    # Полный текст доступен в подсказке, раз его обрезали.
    assert title.tooltip == "ops"


def test_card_title_has_a_readable_minimum_width() -> None:
    """Колонка заголовка не сжимается уже читаемого минимума.

    Это вторая половина защиты от «столбика»: даже с `max_lines` слишком
    узкая колонка нечитаема, поэтому у неё есть нижняя граница.
    """
    from app.ui.SessionCard import CARD_TEXT_MIN_WIDTH

    holders: list[ft.Container] = []

    def visit(node: object) -> None:
        for child in getattr(node, "controls", None) or []:
            visit(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            visit(content)
        if isinstance(node, ft.Container) and node.width:
            holders.append(node)

    visit(SessionCard(_data()).build())
    widths = [holder.width for holder in holders]
    assert CARD_TEXT_MIN_WIDTH in widths, widths
