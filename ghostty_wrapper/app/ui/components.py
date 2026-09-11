# ghostty_wrapper/app/ui/components.py
"""Переиспользуемые UI-компоненты TermoClub."""
from __future__ import annotations

import flet as ft


def show_snack(page: ft.Page, message: str, *, is_error: bool = False) -> None:
    """Показывает SnackBar-уведомление на странице."""
    page.snack_bar = ft.SnackBar(
        ft.Text(message, color=ft.Colors.ERROR if is_error else None),
        bgcolor=ft.Colors.ERROR_CONTAINER if is_error else None,
    )
    page.snack_bar.open = True
    page.update()