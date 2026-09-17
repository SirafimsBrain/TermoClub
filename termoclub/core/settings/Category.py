# termoclub/core/settings/Category.py
"""Категория настроек — «шеврон» в левой панели Settings.

Категория группирует настройки и знает, куда её значения пишутся:
в файл приложения (`~/.termoclub/settings/<slug>.json`) или в папку
плагина. Один класс обслуживает и встроенные, и плагинные категории.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.settings.SettingSpec import SettingSpec
from core.settings.SettingsScope import SettingsScope


@dataclass
class Category:
    """Набор настроек одного раздела окна Settings."""

    slug: str
    title: str
    icon: str = "gear"
    description: str = ""
    order: int = 100
    scope: SettingsScope = SettingsScope.APP
    #: Имя плагина для `scope=plugin` (папка в `~/.termoclub/plugins/`).
    plugin: str = ""
    settings: list[SettingSpec] = field(default_factory=list)
    #: Плагин отключён/недоступен: категория показывается, но только для чтения.
    readonly: bool = False

    @property
    def keys(self) -> list[str]:
        """Ключи настроек категории в порядке объявления."""
        return [spec.key for spec in self.settings]

    def spec(self, key: str) -> SettingSpec | None:
        """Описание настройки по ключу."""
        for item in self.settings:
            if item.key == key:
                return item
        return None

    def defaults(self) -> dict[str, Any]:
        """Значения по умолчанию всех настроек категории."""
        return {spec.key: spec.default for spec in self.settings}

    @classmethod
    def from_dict(cls, payload: dict, *, plugin: str = "") -> "Category":
        """Строит категорию из JSON-файла схемы."""
        if not isinstance(payload, dict):
            raise ValueError("category schema must be an object")
        slug = payload.get("slug")
        if not isinstance(slug, str) or not slug:
            raise ValueError("category schema: missing 'slug'")
        raw_settings = payload.get("settings")
        if not isinstance(raw_settings, dict) or not raw_settings:
            raise ValueError(f"category {slug!r}: 'settings' must be a non-empty object")
        settings = [
            SettingSpec.from_dict(key, spec) for key, spec in raw_settings.items()
        ]
        scope = SettingsScope.PLUGIN if plugin else SettingsScope.APP
        return cls(
            slug=slug,
            title=_title(payload, slug),
            icon=_icon(payload),
            description=_description(payload),
            order=_order(payload),
            scope=scope,
            plugin=plugin,
            settings=settings,
        )


def _title(payload: dict, slug: str) -> str:
    """Заголовок категории (по умолчанию — slug с большой буквы)."""
    value = payload.get("title")
    if isinstance(value, str) and value:
        return value
    return slug.replace("-", " ").replace("_", " ").capitalize()


def _icon(payload: dict) -> str:
    """Имя иконки Font Awesome из схемы."""
    value = payload.get("icon")
    return value if isinstance(value, str) and value else "gear"


def _description(payload: dict) -> str:
    """Подпись категории под заголовком."""
    value = payload.get("description")
    return value if isinstance(value, str) else ""


def _order(payload: dict) -> int:
    """Порядок категории в списке (меньше — выше)."""
    value = payload.get("order")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 100
    return int(value)