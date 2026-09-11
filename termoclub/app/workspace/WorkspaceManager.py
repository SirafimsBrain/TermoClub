# termoclub/app/workspace/WorkspaceManager.py
"""Менеджер сессий рабочей области: список, активная, порядок, состояние.

Чистая логика без Flet-состояния: хранит `WorkspaceItem`, уведомляет
подписчиков (`subscribe`) об изменениях; представление (`TabBar`,
`Stage`, карточки) подписывается и перерисовывается само.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from core.sessions.SessionFactory import SessionFactory
from core.sessions.WorkspaceItem import WorkspaceItem

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Состояние вкладок workspace: создание, закрытие, фокус, порядок."""

    MAX_SESSIONS = 10

    def __init__(self) -> None:
        self._sessions: dict[str, WorkspaceItem] = {}
        self._active_id: str | None = None
        self._listeners: list[Callable[[], None]] = []

    @property
    def sessions(self) -> list[WorkspaceItem]:
        """Сессии в порядке вкладок."""
        return list(self._sessions.values())

    @property
    def active_id(self) -> str | None:
        """Идентификатор активной сессии."""
        return self._active_id

    def subscribe(self, listener: Callable[[], None]) -> None:
        """Подписывает представление на изменения состояния."""
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            listener()

    def get(self, session_id: str) -> WorkspaceItem | None:
        """Возвращает сессию по идентификатору."""
        return self._sessions.get(session_id)

    def get_active(self) -> WorkspaceItem | None:
        """Возвращает активную сессию."""
        if self._active_id is None:
            return None
        return self._sessions.get(self._active_id)

    def open(self, kind: str, page=None, **kwargs) -> WorkspaceItem:
        """Создаёт, активирует и запускает сессию (`page` для pump-задач)."""
        self._enforce_cap()
        item = SessionFactory.create(kind, **kwargs)
        item.on_terminated = self._on_item_terminated
        self._sessions[item.session_id] = item
        if page is not None:
            item.start(page)
        self.activate(item.session_id)
        logger.info("WorkspaceManager: opened %s %s", kind, item.session_id)
        return item

    def close(self, session_id: str) -> None:
        """Останавливает и убирает сессию, чинит активную."""
        item = self._sessions.get(session_id)
        if item is None:
            return
        try:
            item.cleanup()
        except Exception:
            logger.exception("WorkspaceManager: cleanup failed for %s", session_id)
        del self._sessions[session_id]
        if self._active_id == session_id:
            remaining = list(self._sessions.keys())
            self._active_id = remaining[-1] if remaining else None
            active = self.get_active()
            if active is not None:
                active.on_focus()
        logger.info("WorkspaceManager: closed %s", session_id)
        self._notify()

    def activate(self, session_id: str) -> None:
        """Делает сессию активной."""
        if session_id not in self._sessions:
            return
        current = self.get_active()
        if current is not None and current.session_id != session_id:
            current.on_blur()
        self._active_id = session_id
        self._sessions[session_id].on_focus()
        logger.info("WorkspaceManager: activated %s", session_id)
        self._notify()

    def move(self, session_id: str, to_index: int) -> None:
        """Перемещает сессию на позицию (порядок вкладок и карточек)."""
        if session_id not in self._sessions:
            return
        item = self._sessions.pop(session_id)
        ids = list(self._sessions.keys())
        to_index = max(0, min(to_index, len(ids)))
        ids.insert(to_index, session_id)
        self._sessions = {i: (item if i == session_id else self._sessions[i]) for i in ids}
        logger.info("WorkspaceManager: moved %s to %d", session_id, to_index)
        self._notify()

    def _on_item_terminated(self, session_id: str) -> None:
        """Самозавершение сессии (выход шелла) убирает вкладку."""
        logger.info("WorkspaceManager: session terminated %s", session_id)
        self.close(session_id)

    def _enforce_cap(self) -> None:
        """Закрывает старейшие неактивные сессии сверх лимита."""
        while len(self._sessions) >= self.MAX_SESSIONS:
            victim = next(
                (i for i in self._sessions if i != self._active_id), None
            )
            if victim is None:
                break
            logger.warning("WorkspaceManager: cap reached, closing %s", victim)
            self.close(victim)
