# termoclub/core/sessions/SessionStatus.py
"""Статусы жизненного цикла сессии рабочей области."""
from __future__ import annotations

from enum import Enum


class SessionStatus(Enum):
    """Состояние сессии: создана, работает, в фокусе, закрыта, ошибка."""

    CREATED = "created"
    RUNNING = "running"
    FOCUSED = "focused"
    CLOSED = "closed"
    ERROR = "error"
