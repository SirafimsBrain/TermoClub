# termoclub/app/pages/logs.py
"""Заготовка страницы «Логи»."""
from __future__ import annotations

import flet as ft

from app.routes import HOME, LOGS


def logs_view(page: ft.Page) -> ft.View:
    """Возвращает заготовку страницы логов."""
    return ft.View(
        route=LOGS,
        controls=[
            ft.Text("Логи", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Text("Здесь будут отображаться логи приложения."),
            ft.TextButton("На главную", on_click=lambda _: page.go(HOME)),
        ],
    )