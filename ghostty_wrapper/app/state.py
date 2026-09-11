# ghostty_wrapper/app/state.py
"""Минимальное состояние приложения TermoClub."""
from __future__ import annotations


class AppState:
    """Контейнер глобального состояния приложения."""

    def __init__(self) -> None:
        self.active_terminal: str = "ghostty"


state = AppState()