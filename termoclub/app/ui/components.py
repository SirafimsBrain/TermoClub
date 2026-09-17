# termoclub/app/ui/components.py
"""Переиспользуемые UI-компоненты TermoClub."""
from __future__ import annotations

import flet as ft


def show_snack(page: ft.Page, message: str, *, is_error: bool = False) -> None:
    """Показывает SnackBar-уведомление на странице.

    Во Flet 1.0 у `Page` больше нет поля `snack_bar`: уведомление — обычный
    `DialogControl`, который показывается через `page.show_dialog()`.
    Старое `page.snack_bar = ...` на 1.0 не падает (контролы это dataclass'ы
    без запрета новых атрибутов), а молча ничего не показывает — контрол не
    попадает в дерево и не уезжает на клиент. Поэтому ошибка была тихой.

    `show_dialog()` сам выставляет `dialog.open = True` и снимает диалог при
    закрытии, так что отдельное `.open` из старого кода не нужно.
    """
    page.show_dialog(
        ft.SnackBar(
            ft.Text(message, color=ft.Colors.ERROR if is_error else None),
            bgcolor=ft.Colors.ERROR_CONTAINER if is_error else None,
        )
    )
