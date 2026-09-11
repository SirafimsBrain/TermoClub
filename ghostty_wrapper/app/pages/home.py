# ghostty_wrapper/app/pages/home.py
"""Главный экран: действия «Новая вкладка» и «Новое окно»."""
from __future__ import annotations

import flet as ft

from app.routes import HOME, LOGS
from core.config import get_active_terminal_name
from core.terminal.factory import get_terminal_controller
from core.result import Result


def open_new_tab(page: ft.Page) -> None:
    """Открывает новую вкладку активного терминала и показывает результат."""
    result: Result = get_terminal_controller().open_new_tab()
    _show_result(page, result)


def open_new_window(page: ft.Page) -> None:
    """Открывает новое окно активного терминала и показывает результат."""
    result: Result = get_terminal_controller().open_new_window()
    _show_result(page, result)


def _show_result(page: ft.Page, result: Result) -> None:
    """Показывает уведомление по результату вызова контроллера."""
    if result.ok:
        page.snack_bar = ft.SnackBar(ft.Text(result.message))
    else:
        page.snack_bar = ft.SnackBar(
            ft.Text(result.message, color=ft.Colors.ERROR),
            bgcolor=ft.Colors.ERROR_CONTAINER,
        )
    page.snack_bar.open = True
    page.update()


def home_view(page: ft.Page) -> ft.View:
    """Возвращает представление главного экрана."""
    return ft.View(
        route=HOME,
        controls=[
            ft.Text("TermoClub", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Text(f"Активный терминал: {get_active_terminal_name()}"),
            ft.Row(
                [
                    ft.FilledButton(
                        "Новая вкладка",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: open_new_tab(page),
                    ),
                    ft.OutlinedButton(
                        "Новое окно",
                        icon=ft.Icons.OPEN_IN_NEW,
                        on_click=lambda _: open_new_window(page),
                    ),
                ]
            ),
            ft.TextButton("Логи", on_click=lambda _: page.go(LOGS)),
        ],
    )