# termoclub/app/pages/settings.py
"""Вкладка Settings: двухколоночный layout «категории | настройки».

Вкладка открывается как обычная сессия рабочей области (через
`WorkspaceManager`), поэтому здесь только сборка содержимого: слева —
список «шевронов», справа — панель выбранной категории. Значения живут в
`SettingsStore`, изменения применяются `SettingsApplier`.

Класс вкладки (`SettingsSession`) и построение окна (`SettingsPage`)
разнесены: сессия нужна менеджеру workspace, страница — тестам и
headless-сборке контента.
"""
from __future__ import annotations

import flet as ft

from app.ui.settings.CategoryList import CategoryList
from app.ui.settings.LinkOpener import LinkOpener
from app.ui.settings.PathPicker import PathPicker
from app.ui.settings.SettingsControls import SettingsControls
from app.ui.settings.SettingsDeps import SettingsDeps
from app.ui.settings.SettingsPanel import SettingsPanel
from core.settings.SettingsStore import SettingsStore
from core.sessions.WorkspaceItem import WorkspaceItem

#: Slug категории, открытой по умолчанию.
DEFAULT_CATEGORY = "global"


class SettingsPage:
    """Двухколоночный экран настроек (без зависимости от workspace)."""

    def __init__(
        self,
        page: ft.Page,
        store: SettingsStore,
        on_changed=None,
    ) -> None:
        self.page = page
        self.store = store
        self.on_changed = on_changed
        self.deps = SettingsDeps(
            picker=PathPicker(page),
            opener=LinkOpener(page),
        )
        self.sidebar = CategoryList(store, on_select=self._on_category_selected)
        self.controls = SettingsControls(
            page, store, self.deps, on_changed=self._on_value_changed
        )
        self.panel = SettingsPanel(
            page,
            store,
            self.controls,
            on_changed=self._on_value_changed,
            on_plugins_rescanned=self._rebuild_categories,
        )
        self._root = ft.Row(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Settings", style=ft.TextThemeStyle.TITLE_LARGE),
                            ft.Text("Application and plugin settings.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                    ),
                    padding=ft.Padding.all(12),
                ),
                self.sidebar.control,
                ft.VerticalDivider(width=1),
                self.panel.control,
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        #: Хранилище уведомляет только о том, что значения поменялись.
        self.store.subscribe(self._on_store_changed)
        self._rebuild_categories()

    @property
    def control(self) -> ft.Control:
        """Корневой контрол вкладки."""
        return self._root

    @property
    def picker(self) -> PathPicker:
        """Сервис диалогов выбора пути (для тестов и диагностики)."""
        return self.deps.picker

    def select(self, slug: str) -> None:
        """Открывает категорию по slug."""
        self._on_category_selected(slug)

    def refresh(self) -> None:
        """Перечитывает схему и значения (внешние правки файлов)."""
        self._rebuild_categories()
        self.panel.refresh()

    def dispose(self) -> None:
        """Отписывается от хранилища: вкладка закрыта, ссылки не держим."""
        self.store.unsubscribe(self._on_store_changed)

    # --- События ---

    def _on_category_selected(self, slug: str) -> None:
        """Показывает выбранную категорию справа."""
        self.panel.set_categories(self.store.categories)
        self.panel.show(slug)
        self.sidebar.select(self.panel.slug)

    def _on_value_changed(self, slug: str, key: str) -> None:
        """Значение изменено: обновляет пометки и отдаёт событие наружу."""
        self.sidebar.refresh()
        if self.on_changed is not None:
            self.on_changed(slug, key)

    def _on_store_changed(self) -> None:
        """Хранилище изменилось (в т.ч. извне) — синхронизирует панели."""
        self.sidebar.refresh()

    def _rebuild_categories(self) -> None:
        """Пересобирает левую панель и открывает категорию по умолчанию."""
        categories = self.store.categories
        self.sidebar.rebuild(categories)
        self.panel.set_categories(categories)
        slug = self.panel.slug or DEFAULT_CATEGORY
        self._on_category_selected(slug)


class SettingsSession(WorkspaceItem):
    """Вкладка Settings в рабочей области (обычная сессия workspace)."""

    KIND = "settings"

    def __init__(
        self,
        store: SettingsStore | None = None,
        title: str = "Settings",
        session_id: str | None = None,
        page: ft.Page | None = None,
        on_changed=None,
    ) -> None:
        super().__init__(title, session_id)
        self._store = store or SettingsStore()
        self._page_ref = page
        self._page_view: SettingsPage | None = None
        self._on_changed = on_changed

    @property
    def icon(self) -> str:
        """Иконка вкладки (шестерёнка)."""
        return "gear"

    @property
    def store(self) -> SettingsStore:
        """Хранилище настроек, которым пользуется вкладка."""
        return self._store

    @property
    def view(self) -> SettingsPage | None:
        """Экран настроек (создаётся при построении контента)."""
        return self._page_view

    def start(self, page: ft.Page) -> None:
        """Запоминает страницу для сервисов (диалоги, буфер обмена)."""
        self._page_ref = page

    def get_content(self) -> ft.Control:
        """Строит экран настроек один раз и кэширует его."""
        if self._content is None:
            if self._page_ref is None:
                raise RuntimeError("SettingsSession requires a page to build its UI")
            self._page_view = SettingsPage(
                self._page_ref, self._store, on_changed=self._on_changed
            )
            self._content = self._page_view.control
        return self._content

    def refresh(self) -> None:
        """Перечитывает значения настроек и обновляет виджеты."""
        if self._page_view is not None:
            self._page_view.refresh()

    def cleanup(self) -> None:
        """Отписывается от хранилища и отпускает построенный экран.

        Кэш контента сбрасывается: если вкладку когда-нибудь переиспользуют
        после закрытия, экран соберётся заново вместе с подпиской.
        """
        if self._page_view is not None:
            self._page_view.dispose()
            self._page_view = None
        self._content = None
        from core.sessions.SessionStatus import SessionStatus

        self._status = SessionStatus.CLOSED