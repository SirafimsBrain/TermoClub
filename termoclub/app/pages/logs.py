# termoclub/app/pages/logs.py
"""Заготовка страницы «Логи»."""
from __future__ import annotations

import flet as ft

from app.routes import HOME, LOGS


def logs_content(page: ft.Page) -> ft.Control:
    """Возвращает контент страницы логов для центральной рабочей области."""

    async def go_home(_: ft.ControlEvent) -> None:
        await page.push_route(HOME)

    return ft.Column(
        [
            # `theme_style`, а не `style`: во Flet `style` — это `TextStyle`,
            # строка из `TextThemeStyle` ломала отрисовку на клиенте.
            ft.Text("Логи", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Text("Здесь будут отображаться логи приложения."),
            ft.TextButton("На главную", on_click=go_home),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def logs_view(page: ft.Page) -> ft.View:
    """Возвращает заготовку страницы логов."""

    async def go_home(_: ft.ControlEvent) -> None:
        await page.push_route(HOME)

    return ft.View(
        route=LOGS,
        controls=[logs_content(page)],
    )
