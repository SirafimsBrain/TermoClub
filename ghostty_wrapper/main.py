# ghostty_wrapper/main.py
"""TermoClub — точка входа приложения.

Запускает Flet-приложение с маршрутизацией и главным экраном.
"""
from __future__ import annotations

import flet as ft

from logging_setup import setup_logging


def main(page: ft.Page) -> None:
    """Настройка страницы и запуск приложения."""
    setup_logging()
    page.title = "TermoClub"
    page.theme_mode = ft.ThemeMode.DARK
    page.on_route_change = route_change
    page.go("/")


def route_change(route: ft.RouteChangeEvent) -> None:
    """Обрабатывает смену маршрута и строит соответствующую страницу."""
    page = route.page
    page.views.clear()

    if route.route == "/logs":
        from app.pages.logs import logs_view

        page.views.append(logs_view(page))
    else:
        from app.pages.home import home_view

        page.views.append(home_view(page))

    page.update()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)