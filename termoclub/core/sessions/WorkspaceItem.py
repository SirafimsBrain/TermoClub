# termoclub/core/sessions/WorkspaceItem.py
"""Абстрактная сессия рабочей области (вкладка)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from uuid import uuid4

import flet as ft

from core.sessions.SessionStatus import SessionStatus


class WorkspaceItem(ABC):
    """Интерфейс вкладки: логика здесь, Flet-контрол только отображение.

    Контрол строится лениво в `get_content()` один раз и кэшируется
    наследником; тяжёлый запуск — в `start()` (через `page.run_task()`).
    """

    KIND = "unknown"

    def __init__(self, title: str, session_id: str | None = None) -> None:
        self._session_id = session_id or str(uuid4())
        self._title = title
        self._status = SessionStatus.CREATED
        self._content: ft.Control | None = None
        #: Вызывается при самозавершении сессии (например, выход шелла).
        self.on_terminated: Callable[[str], None] | None = None

    @property
    def session_id(self) -> str:
        """Уникальный идентификатор сессии."""
        return self._session_id

    @property
    def kind(self) -> str:
        """Тип сессии для фабрики и бейджей (`terminal`, `editor`, ...)."""
        return self.KIND

    @property
    def title(self) -> str:
        """Заголовок вкладки/карточки."""
        return self._title

    @property
    def icon(self) -> str:
        """Имя иконки Font Awesome для вкладки/карточки."""
        return "circle-info"

    @property
    def status(self) -> SessionStatus:
        """Текущий статус сессии."""
        return self._status

    @property
    def can_close(self) -> bool:
        """Можно ли закрыть сессию пользователем."""
        return True

    def set_title(self, title: str) -> None:
        """Переименовывает сессию."""
        self._title = title

    def start(self, page: ft.Page) -> None:
        """Запускает сессию (по умолчанию — ничего, переопределить при нужде)."""

    @abstractmethod
    def get_content(self) -> ft.Control:
        """Возвращает (строя при первом вызове) контрол отображения."""

    def on_focus(self) -> None:
        """Вызывается при активации вкладки."""
        if self._status == SessionStatus.RUNNING:
            self._status = SessionStatus.FOCUSED

    def on_blur(self) -> None:
        """Вызывается при потере фокуса вкладкой."""
        if self._status == SessionStatus.FOCUSED:
            self._status = SessionStatus.RUNNING

    @abstractmethod
    def cleanup(self) -> None:
        """Останавливает сессию и освобождает ресурсы (синхронно)."""
