# termoclub/app/pages/home.py
"""Главный экран: действия «Новая вкладка» и «Новое окно»."""
from __future__ import annotations

import flet as ft

from app.routes import HOME, LOGS
from app.ui.components import show_snack
from core.config import get_active_terminal_name
from core.terminal.factory import get_terminal_controller
from core.result import Result


def open_new_tab(page: ft.Page, on_status: object = None) -> None:
    """Открывает новую вкладку активного терминала и показывает результат."""
    result: Result = get_terminal_controller().open_new_tab()
    _show_result(page, result, on_status)


def open_new_window(page: ft.Page, on_status: object = None) -> None:
    """Открывает новое окно активного терминала и показывает результат."""
    result: Result = get_terminal_controller().open_new_window()
    _show_result(page, result, on_status)


def _show_result(page: ft.Page, result: Result, on_status: object = None) -> None:
    """Показывает уведомление по результату вызова контроллера."""
    show_snack(page, result.message, is_error=not result.ok)
    if on_status is not None:
        on_status(result.message)


def home_content(page: ft.Page, on_status: object = None) -> ft.Control:
    """Возвращает контент главного экрана для центральной рабочей области."""

    async def open_logs(_: ft.ControlEvent) -> None:
        await page.push_route(LOGS)

    return ft.Column(
        [
            # `theme_style`, а не `style`: во Flet `style` — это `TextStyle`,
            # строка из `TextThemeStyle` ломала отрисовку на клиенте.
            ft.Text("TermoClub", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Text(f"Активный терминал: {get_active_terminal_name()}"),
            ft.Row(
                [
                    ft.FilledButton(
                        "Новая вкладка",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: open_new_tab(page, on_status),
                    ),
                    ft.OutlinedButton(
                        "Новое окно",
                        icon=ft.Icons.OPEN_IN_NEW,
                        on_click=lambda _: open_new_window(page, on_status),
                    ),
                ]
            ),
            ft.TextButton("Логи", on_click=open_logs),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def home_view(page: ft.Page) -> ft.View:
    """Возвращает представление главного экрана (совместимость без layout)."""

    async def open_logs(_: ft.ControlEvent) -> None:
        await page.push_route(LOGS)

    return ft.View(
        route=HOME,
        controls=[home_content(page)],
    )