# termoclub/app/ui/SessionCardData.py
"""Дескриптор сессии для вкладок и карточек (UI не трогает сессии)."""
from __future__ import annotations

from dataclasses import dataclass

from core.sessions.SessionStatus import SessionStatus
from core.sessions.WorkspaceItem import WorkspaceItem


@dataclass
class SessionCardData:
    """Плоские данные для отрисовки вкладки/карточки."""

    session_id: str
    title: str
    kind: str
    source: str
    status: SessionStatus
    icon: str
    active: bool = False
    can_close: bool = True

    @classmethod
    def from_item(
        cls, item: WorkspaceItem, active: bool = False, source: str = "workspace"
    ) -> "SessionCardData":
        """Строит дескриптор из сессии (и будущий from_external — из хендла)."""
        return cls(
            session_id=item.session_id,
            title=item.title,
            kind=item.kind,
            source=source,
            status=item.status,
            icon=item.icon,
            active=active,
            can_close=item.can_close,
        )
