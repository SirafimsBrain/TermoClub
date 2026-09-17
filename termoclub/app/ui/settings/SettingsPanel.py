# termoclub/app/ui/settings/SettingsPanel.py
"""Правая панель Settings: содержимое выбранной категории.

Панель собирает строки настроек через фабрику контролов (`SettingsControls`)
и показывает их вместе с заголовком категории и общими действиями
(«Сохранить всё», «Сбросить категорию», «Обновить список плагинов»).
Сами значения панель не хранит: всё идёт через `SettingsStore`.
"""
from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui.settings.SettingControl import MUTED, SettingControl
from app.ui.settings.SettingsControls import SettingsControls
from core.settings.Category import Category
from core.settings.SettingsError import SettingsError
from core.settings.SettingsStore import SettingsStore


class SettingsPanel:
    """Контент категории: заголовок, настройки и действия."""

    def __init__(
        self,
        page: ft.Page,
        store: SettingsStore,
        controls: SettingsControls,
        on_changed: Callable[[str, str], None] | None = None,
        on_plugins_rescanned: Callable[[], None] | None = None,
    ) -> None:
        self.page = page
        self.store = store
        self.controls = controls
        self.on_changed = on_changed
        self.on_plugins_rescanned = on_plugins_rescanned
        self._rows: list[SettingControl] = []
        self._categories: list[Category] = []
        self._slug = ""
        self._body = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        # `theme_style` (не `style`): `style` ждёт `TextStyle`, а клиент
        # разбирает его как map — строка из enum роняла отрисовку панели.
        self._title = ft.Text("", theme_style=ft.TextThemeStyle.TITLE_LARGE)
        self._description = ft.Text("", size=12, color=MUTED)
        self._actions = ft.Row(spacing=8)
        self._root = ft.Column(
            [
                ft.Column([self._title, self._description], spacing=2),
                self._actions,
                ft.Divider(),
                self._body,
            ],
            spacing=8,
            expand=True,
        )

    @property
    def control(self) -> ft.Control:
        """Контент правой колонки."""
        return ft.Container(content=self._root, expand=True, padding=ft.Padding.only(left=16, top=8, right=16))

    @property
    def slug(self) -> str:
        """Slug показанной категории."""
        return self._slug

    @property
    def rows(self) -> list[SettingControl]:
        """Контролы настроек текущей категории."""
        return list(self._rows)

    def set_categories(self, categories: list[Category]) -> None:
        """Запоминает доступные категории (для выбора по умолчанию)."""
        self._categories = list(categories)

    def show(self, slug: str) -> None:
        """Рисует настройки категории (пустой slug — первая доступная)."""
        category = self._pick(slug)
        if category is None:
            self._show_empty()
            return
        self._slug = category.slug
        self._title.value = category.title
        self._description.value = self._description_text(category)
        self._actions.controls = self._build_actions(category)
        self._rows = [
            self.controls.build(category, spec) for spec in category.settings
        ]
        self._body.controls = [row.control for row in self._rows]
        self._safe_update(self._root)

    def refresh(self) -> None:
        """Перечитывает значения в текущих строках (внешние правки, сброс)."""
        for row in self._rows:
            row.show_value(row.value)
            row.refresh_reset()

    # --- Заголовок и действия ---

    def _description_text(self, category: Category) -> str:
        """Описание категории с пометками о плагине и режиме «только чтение»."""
        parts = [category.description] if category.description else []
        if category.scope.value == "plugin":
            parts.append(f"plugin: {category.plugin}")
        if category.readonly:
            parts.append("read-only")
        if self.store.readonly:
            parts.append("profile is not writable")
        return " · ".join(parts)

    def _build_actions(self, category: Category) -> list[ft.Control]:
        """Кнопки категории: сохранить, сбросить, обновить плагины."""
        actions: list[ft.Control] = []
        if not self.store.readonly:
            actions.append(
                ft.FilledButton(
                    "Save all",
                    icon=ft.Icons.SAVE,
                    disabled=not self.store.dirty_keys,
                    on_click=self._on_save,
                )
            )
            actions.append(
                ft.OutlinedButton(
                    "Reset category",
                    icon=ft.Icons.RESTART_ALT,
                    on_click=lambda _e: self._on_reset_category(category),
                )
            )
        if category.slug == "plugins":
            actions.append(
                ft.OutlinedButton(
                    "Rescan plugins",
                    icon=ft.Icons.REFRESH,
                    on_click=self._on_rescan,
                )
            )
        return actions

    # --- Действия ---

    def _on_save(self, _event: ft.ControlEvent) -> None:
        """Пишет все несохранённые правки в файлы профиля."""
        try:
            self.store.save_all()
        except SettingsError as exc:
            self._message(str(exc), error=True)
            return
        self._message("Settings saved")

    def _on_reset_category(self, category: Category) -> None:
        """Сбрасывает категорию к умолчаниям и перерисовывает её."""
        try:
            self.store.reset_category(category.slug)
        except SettingsError as exc:
            self._message(str(exc), error=True)
            return
        if self.on_changed is not None:
            for spec in category.settings:
                self.on_changed(category.slug, spec.key)
        self.show(category.slug)
        self._message(f"Category {category.title} reset")

    def _on_rescan(self, _event: ft.ControlEvent) -> None:
        """Пересканирует папки плагинов и пересобирает вкладку."""
        try:
            found = self.store.refresh_plugins()
        except SettingsError as exc:
            self._message(str(exc), error=True)
            return
        if self.on_plugins_rescanned is not None:
            self.on_plugins_rescanned()
        self._message(f"Plugins found: {len(found)}")

    # --- Служебное ---

    def _pick(self, slug: str) -> Category | None:
        """Категория по slug, иначе первая доступная."""
        if slug:
            found = self.store.schema.find(slug)
            if found is not None:
                return found
        return self._categories[0] if self._categories else None

    def _show_empty(self) -> None:
        """Состояние «настроек нет» (пустая схема)."""
        self._slug = ""
        self._title.value = "Settings"
        self._description.value = "No settings categories are available."
        self._actions.controls = []
        self._rows = []
        self._body.controls = [ft.Text("Nothing to configure.", color=MUTED)]
        self._safe_update(self._root)

    def _message(self, message: str, *, error: bool = False) -> None:
        """Показывает результат действия в снекбаре."""
        from app.ui.components import show_snack

        show_snack(self.page, message, is_error=error)

    @staticmethod
    def _safe_update(control: ft.Control | None) -> None:
        """Обновляет контрол, если он уже примонтирован к странице."""
        if control is None:
            return
        try:
            control.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.