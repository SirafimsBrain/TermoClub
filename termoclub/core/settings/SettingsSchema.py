# termoclub/core/settings/SettingsSchema.py
"""Схема настроек: категории приложения + категории плагинов.

Одна схема на всё приложение. Плагинные категории попадают в неё двумя
путями: встроенные (из `settings/plugins/<plugin>.json` в составе
приложения) и обнаруженные на диске (`scanner.py`). Схема не трогает
файлы значений — только описывает, что и как можно настраивать.
"""
from __future__ import annotations

import copy
from collections.abc import Iterable

from core.settings.Category import Category
from core.settings.SettingsError import SettingsError
from core.settings.SettingsScope import SettingsScope


class SettingsSchema:
    """Упорядоченный набор категорий настроек."""

    def __init__(self, categories: Iterable[Category] = ()) -> None:
        self._categories: list[Category] = []
        for category in categories:
            self.add(category)

    def add(self, category: Category) -> None:
        """Добавляет категорию (повторный slug вытесняет прежнюю)."""
        if self.find(category.slug) is not None:
            raise SettingsError(f"duplicate settings category: {category.slug!r}")
        self._categories.append(category)
        self._categories.sort(key=lambda item: (item.order, item.title.lower()))

    @property
    def categories(self) -> list[Category]:
        """Категории в порядке отображения."""
        return list(self._categories)

    def category_models(self) -> list[Category]:
        """Копии категорий схемы: пересканирование их не портит."""
        return copy.deepcopy(self._categories)

    @property
    def app_categories(self) -> list[Category]:
        """Только категории приложения."""
        return [c for c in self._categories if c.scope is SettingsScope.APP]

    @property
    def plugin_categories(self) -> list[Category]:
        """Только категории плагинов."""
        return [c for c in self._categories if c.scope is SettingsScope.PLUGIN]

    def find(self, slug: str) -> Category | None:
        """Категория по slug."""
        for category in self._categories:
            if category.slug == slug:
                return category
        return None

    def require(self, slug: str) -> Category:
        """Категория по slug; отсутствие — ошибка схемы."""
        category = self.find(slug)
        if category is None:
            raise SettingsError(f"unknown settings category: {slug!r}")
        return category

    def replace(self, category: Category) -> None:
        """Заменяет категорию с тем же slug (пересканирование плагинов)."""
        self._categories = [c for c in self._categories if c.slug != category.slug]
        self.add(category)

    def spec(self, key: str) -> tuple[Category, object] | None:
        """Ищет настройку по полному ключу `slug.key`."""
        slug, _, name = key.partition(".")
        category = self.find(slug)
        if category is None:
            return None
        spec = category.spec(name)
        return None if spec is None else (category, spec)