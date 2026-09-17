# termoclub/app/ui/settings/CategoryList.py
"""Левая панель Settings: вертикальный список «шевронов»-категорий.

Один «шеврон» — миникарточка категории: иконка, заголовок и пометки
(изменённые настройки, плагин недоступен). Список строится по схеме и
пересобирается после пересканирования плагинов, поэтому новые категории
появляются без правок этого класса.
"""
from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui.FontAwesome import FontAwesome
from app.ui.settings.SettingControl import MUTED
from core.settings.Category import Category
from core.settings.SettingsStore import SettingsStore


class CategoryList:
    """Список категорий настроек (левая колонка вкладки)."""

    WIDTH = 220

    def __init__(
        self,
        store: SettingsStore,
        on_select: Callable[[str], None],
    ) -> None:
        self.store = store
        self.on_select = on_select
        self._active = ""
        self._rows: dict[str, ft.Container] = {}
        self._column = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)

    @property
    def control(self) -> ft.Control:
        """Колонка категорий."""
        return ft.Container(width=self.WIDTH, content=self._column)

    @property
    def active(self) -> str:
        """Slug выбранной категории."""
        return self._active

    def select(self, slug: str) -> None:
        """Отмечает категорию выбранной (без вызова `on_select`)."""
        self._active = slug
        for category_slug, row in self._rows.items():
            row.bgcolor = self._row_color(category_slug)
            self._safe_update(row)

    def rebuild(self, categories: list[Category]) -> None:
        """Пересобирает список категорий (порядок — из схемы)."""
        self._rows.clear()
        self._column.controls = [self._row(category) for category in categories]
        self._safe_update(self._column)

    def refresh(self) -> None:
        """Обновляет пометки строк (например, «изменено») без пересборки."""
        for slug, row in self._rows.items():
            row.bgcolor = self._row_color(slug)
            row.content.controls[2].visible = self._is_modified(slug)
            self._safe_update(row)

    # --- Строка категории ---

    def _row(self, category: Category) -> ft.Container:
        """«Шеврон» одной категории."""
        title = ft.Text(category.title, size=13, weight=ft.FontWeight.W_500)
        dot = ft.Container(
            width=6,
            height=6,
            border_radius=3,
            bgcolor=ft.Colors.PRIMARY,
            visible=self._is_modified(category.slug),
        )
        row = ft.Container(
            padding=ft.Padding.symmetric(vertical=8, horizontal=10),
            border_radius=6,
            bgcolor=self._row_color(category.slug),
            on_click=lambda _e, slug=category.slug: self._click(slug),
            content=ft.Row(
                [
                    FontAwesome.icon(category.icon, size=14),
                    ft.Column(
                        [title, self._subtitle(category)],
                        spacing=0,
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    dot,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        self._rows[category.slug] = row
        return row

    def _subtitle(self, category: Category) -> ft.Control:
        """Подпись категории: тип (плагин/приложение) или описание."""
        if category.scope.value == "plugin":
            text = f"plugin · {category.plugin}"
        else:
            text = category.description or f"{len(category.settings)} settings"
        return ft.Text(text, size=10, color=MUTED, max_lines=1)

    def _click(self, slug: str) -> None:
        """Выбор категории пользователем."""
        self.select(slug)
        self.on_select(slug)

    def _row_color(self, slug: str) -> str | None:
        """Подсветка выбранной строки."""
        if slug != self._active:
            return None
        return ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)

    def _is_modified(self, slug: str) -> bool:
        """True, если в категории есть настройки, отличные от умолчаний."""
        return any(key.startswith(f"{slug}.") for key in self.store.modified())

    @staticmethod
    def _safe_update(control: ft.Control | None) -> None:
        """Обновляет контрол, если он уже примонтирован к странице."""
        if control is None:
            return
        try:
            control.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.