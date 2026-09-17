# termoclub/core/settings/SettingsStore.py
"""Класс-посредник между файловыми операциями и GUI.

Единственный вход в настройки для всего приложения: чтение, запись,
валидация типов, слияние слоёв, поиск по категориям, сброс к умолчаниям.
GUI-слой (`app/ui/settings`) работает только через него и ничего не знает
про файлы и `FileManager`.

Слои значений (от слабого к сильному):

1. встроенная схема в составе приложения (`schema/*.json`) — умолчания;
2. файлы профиля пользователя (`~/.termoclub/settings/*.json`) — приоритет
   над встроенными;
3. ещё не сохранённые правки пользователя в текущей сессии (dirty).

Если профиль недоступен (не создан и не создаётся — read-only домашний
каталог), хранилище работает в режиме «только чтение»: значения берутся
из встроенной схемы, запись отклоняется `SettingsError`.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.settings.Category import Category
from core.settings.Choice import Choice
from core.settings.PluginInfo import PluginInfo
from core.settings.SchemaLoader import SchemaLoader
from core.settings.SettingSpec import SettingSpec
from core.settings.SettingsError import SettingsError
from core.settings.SettingsSchema import SettingsSchema
from core.settings.SettingsScope import SettingsScope
from core.settings.SettingsValidationError import SettingsValidationError
from core.settings.ValueCodec import ValueCodec
from core.storage.FileManager import FileManager

logger = logging.getLogger(__name__)

#: Относительный путь к папке настроек приложения внутри профиля.
SETTINGS_DIR = "settings"

#: Относительный путь к папке плагинов внутри профиля.
PLUGINS_DIR = "plugins"

#: Имя файла со значениями настроек плагина.
PLUGIN_VALUES_FILE = "values.json"


class SettingsStore:
    """Стандартизированная работа с настройками поверх `FileManager`."""

    def __init__(
        self,
        file_manager: FileManager | None = None,
        schema: SettingsSchema | None = None,
        loader: SchemaLoader | None = None,
    ) -> None:
        self._fm = file_manager or self._open_file_manager()
        self._loader = loader or SchemaLoader()
        self._base_schema = schema if schema is not None else self._loader.load_app_schema()
        self._schema = self._base_schema
        self._values: dict[str, dict[str, Any]] = {}
        self._defaults: dict[str, dict[str, Any]] = {}
        self._dirty: set[str] = set()
        self._readonly = self._fm is None
        self._listeners: list[Callable[[], None]] = []
        self._change_listeners: list[Callable[[str, str], None]] = []
        self._load()

    # --- Схема ---

    @property
    def schema(self) -> SettingsSchema:
        """Активная схема (категории приложения и плагинов)."""
        return self._schema

    @property
    def categories(self) -> list[Category]:
        """Категории в порядке отображения."""
        return self._schema.categories

    @property
    def readonly(self) -> bool:
        """True, если профиль недоступен и запись невозможна."""
        return self._readonly

    @property
    def dirty_keys(self) -> set[str]:
        """Полные ключи (`slug.key`) с несохранёнными правками."""
        return set(self._dirty)

    @property
    def listener_count(self) -> int:
        """Число активных подписчиков (диагностика забытых подписок)."""
        return len(self._listeners)

    def replace_schema(self, schema: SettingsSchema) -> None:
        """Подменяет схему (после пересканирования плагинов) и перечитывает."""
        self._schema = schema
        self._values.clear()
        self._defaults.clear()
        self._dirty.clear()
        self._load()
        self._notify()

    def refresh_plugins(self, scanner: object | None = None) -> list[PluginInfo]:
        """Пересканирует плагины и подхватывает их настройки.

        Сканер отдаёт список найденных плагинов; их имена становятся
        вариантами настройки `plugins.disabled_plugins`, а схемы плагинов —
        новыми категориями. Правки, сделанные в GUI до пересканирования,
        сохраняются.
        """
        from core.settings.PluginSettingsScanner import PluginSettingsScanner

        if self._fm is None:
            logger.warning("SettingsStore: no profile, plugins are not scanned")
            return []
        scanner = scanner or PluginSettingsScanner(
            self._fm, self._loader, directory=self._plugin_directory()
        )
        dirty = dict(self._values)
        dirty_keys = set(self._dirty)
        schema = SettingsSchema(self._base_schema.category_models())
        disabled = set()
        plugins_category = schema.find("plugins")
        if plugins_category is not None:
            spec = plugins_category.spec("disabled_plugins")
            if spec is not None:
                disabled = set(self.get("plugins", "disabled_plugins") or [])
        scanner.scan(schema, disabled)
        if plugins_category is not None:
            spec = plugins_category.spec("disabled_plugins")
            if spec is not None:
                spec.choices = [
                    Choice(value=name, label=name) for name in scanner.names()
                ]
        self._schema = schema
        self._values.clear()
        self._defaults.clear()
        self._dirty.clear()
        self._load()
        for slug, values in dirty.items():
            if slug in self._values:
                self._values[slug].update(values)
        self._dirty = {key for key in dirty_keys if key in self._known_keys()}
        logger.info(
            "SettingsStore: plugins refreshed, %d plugin categories",
            len(self._schema.plugin_categories),
        )
        self._notify()
        return scanner.plugins

    def subscribe(self, listener: Callable[[], None]) -> None:
        """Подписывает GUI на изменения значений."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[], None]) -> None:
        """Снимает подписку на изменения значений (вкладка закрыта)."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def subscribe_changes(self, listener: Callable[[str, str], None]) -> None:
        """Подписывает на изменения конкретных настроек: `listener(slug, key)`.

        Этим каналом пользуется `SettingsApplier`: ему важно знать, *что*
        именно поменялось, чтобы применить это к живым терминалам.
        """
        if listener not in self._change_listeners:
            self._change_listeners.append(listener)

    def unsubscribe_changes(self, listener: Callable[[str, str], None]) -> None:
        """Снимает подписку на изменения конкретных настроек."""
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    # --- Чтение ---

    def get(self, slug: str, key: str) -> Any:
        """Текущее значение настройки (dirty -> профиль -> умолчание)."""
        category = self._schema.require(slug)
        spec = category.spec(key)
        if spec is None:
            raise SettingsError(f"unknown setting: {slug}.{key}")
        if f"{slug}.{key}" in self._dirty:
            return self._values[slug][key]
        return self._current(category, spec)

    def get_full(self, full_key: str) -> Any:
        """Значение по полному ключу `slug.key`."""
        slug, _, key = full_key.partition(".")
        return self.get(slug, key)

    def default(self, slug: str, key: str) -> Any:
        """Умолчание настройки из встроенной схемы."""
        return self._defaults[slug][key]

    def is_modified(self, slug: str, key: str) -> bool:
        """True, если значение отличается от умолчания."""
        return self.get(slug, key) != self.default(slug, key)

    def values(self, slug: str) -> dict[str, Any]:
        """Все значения категории (для применения и экспорта)."""
        category = self._schema.require(slug)
        return {spec.key: self.get(slug, spec.key) for spec in category.settings}

    def all_values(self) -> dict[str, dict[str, Any]]:
        """Значения всех категорий: `{slug: {key: value}}`."""
        return {category.slug: self.values(category.slug) for category in self.categories}

    def find(self, query: str) -> list[tuple[Category, SettingSpec]]:
        """Поиск настроек по ключу/подписи/описанию (без учёта регистра)."""
        needle = query.strip().lower()
        if not needle:
            return []
        found: list[tuple[Category, SettingSpec]] = []
        for category in self.categories:
            for spec in category.settings:
                haystack = " ".join(
                    (spec.key, spec.title, spec.description, category.title)
                ).lower()
                if needle in haystack:
                    found.append((category, spec))
        return found

    def modified(self) -> list[str]:
        """Полные ключи настроек, отличающихся от умолчаний."""
        result: list[str] = []
        for category in self.categories:
            for spec in category.settings:
                if self.is_modified(category.slug, spec.key):
                    result.append(f"{category.slug}.{spec.key}")
        return result

    # --- Запись ---

    def set(self, slug: str, key: str, value: Any, *, save: bool = False) -> Any:
        """Проверяет и запоминает значение; `save=True` пишет файл сразу."""
        category = self._schema.require(slug)
        spec = category.spec(key)
        if spec is None:
            raise SettingsError(f"unknown setting: {slug}.{key}")
        if spec.readonly or category.readonly:
            raise SettingsError(f"setting {slug}.{key} is read-only")
        if self._readonly:
            raise SettingsError(
                "user profile is not writable; settings cannot be changed"
            )
        coerced = ValueCodec.coerce(spec, value)
        current = self._current(category, spec)
        if coerced == current:
            return coerced
        self._values[slug][key] = coerced
        self._dirty.add(f"{slug}.{key}")
        logger.info("SettingsStore: %s.%s = %r", slug, key, coerced)
        if save:
            self.save_category(slug)
        self._notify_changed(slug, key)
        self._notify()
        return coerced

    def set_many(self, values: dict[str, Any], *, save: bool = False) -> list[str]:
        """Пакетная запись по полным ключам; возвращает список ошибок."""
        errors: list[str] = []
        touched: set[str] = set()
        for full_key, value in values.items():
            slug, _, key = full_key.partition(".")
            try:
                self.set(slug, key, value)
                touched.add(slug)
            except SettingsValidationError as exc:
                errors.append(str(exc))
                logger.warning("SettingsStore: rejected %s: %s", full_key, exc)
        if save:
            for slug in sorted(touched):
                self.save_category(slug)
        return errors

    def reset(self, slug: str, key: str, *, save: bool = False) -> Any:
        """Возвращает настройку к умолчанию (убирает её из файла профиля)."""
        category = self._schema.require(slug)
        spec = category.spec(key)
        if spec is None:
            raise SettingsError(f"unknown setting: {slug}.{key}")
        default = self._defaults[slug][key]
        stored = self._stored(category)
        if key in stored:
            del stored[key]
            self._persist(category, stored)
        self._values[slug][key] = default
        self._dirty.discard(f"{slug}.{key}")
        if save:
            self.save_category(slug)
        logger.info("SettingsStore: reset %s.%s", slug, key)
        self._notify_changed(slug, key)
        self._notify()
        return default

    def reset_category(self, slug: str) -> None:
        """Сбрасывает всю категорию к умолчаниям и удаляет её файл."""
        category = self._schema.require(slug)
        for spec in category.settings:
            self._values[slug][spec.key] = self._defaults[slug][spec.key]
            self._dirty.discard(f"{slug}.{spec.key}")
        self._persist(category, {})
        logger.info("SettingsStore: reset category %s", slug)
        for spec in category.settings:
            self._notify_changed(slug, spec.key)
        self._notify()

    def save_category(self, slug: str) -> None:
        """Пишет значения категории в её файл (только отличия от умолчаний)."""
        category = self._schema.require(slug)
        payload: dict[str, Any] = {}
        for spec in category.settings:
            value = self._values[slug][spec.key]
            if value != self._defaults[slug][spec.key]:
                payload[spec.key] = ValueCodec.to_json(spec, value)
        self._persist(category, payload)
        self._dirty = {k for k in self._dirty if not k.startswith(f"{slug}.")}
        logger.info("SettingsStore: saved %s (%d keys)", slug, len(payload))

    def save_all(self) -> None:
        """Пишет все категории, где есть несохранённые правки."""
        slugs = {key.partition(".")[0] for key in self._dirty}
        for slug in sorted(slugs):
            self.save_category(slug)

    # --- Служебное ---

    def path_for(self, category: Category) -> Path:
        """Путь к файлу значений категории внутри профиля."""
        if category.scope is SettingsScope.PLUGIN:
            return Path(self._plugin_directory()) / category.plugin / PLUGIN_VALUES_FILE
        return Path(SETTINGS_DIR) / f"{category.slug}.json"

    def reload(self) -> None:
        """Перечитывает файлы профиля (внешние правки)."""
        self._values.clear()
        self._defaults.clear()
        self._dirty.clear()
        self._load()
        self._notify()

    def _open_file_manager(self) -> FileManager | None:
        """Открывает `FileManager` профиля; недоступность — режим read-only."""
        try:
            return FileManager()
        except (OSError, ValueError, NotImplementedError) as exc:
            logger.error("SettingsStore: profile is unavailable: %s", exc)
            return None

    def _plugin_directory(self) -> str:
        """Папка плагинов из настроек: пользовательская, иначе профиль.

        `FileManager` резолвит только относительные пути внутри профиля,
        поэтому абсолютный путь в настройке не используется — о нём пишем
        в лог, а сканирование идёт по профилю.
        """
        configured = ""
        if self._schema.find("plugins") is not None:
            configured = self.get("plugins", "plugin_directory") or ""
        configured = str(configured).strip()
        if not configured:
            return PLUGINS_DIR
        if Path(configured).is_absolute():
            logger.warning(
                "SettingsStore: plugin_directory %r is absolute, using %r",
                configured,
                PLUGINS_DIR,
            )
            return PLUGINS_DIR
        return configured

    def _load(self) -> None:
        """Готовит умолчания и читает слои профиля."""
        for category in self.categories:
            self._defaults[category.slug] = {
                spec.key: ValueCodec.coerce(spec, spec.default)
                for spec in category.settings
            }
            self._values[category.slug] = dict(self._defaults[category.slug])
        if not self._prepare_profile():
            logger.warning(
                "SettingsStore: profile storage is unavailable, using built-in defaults"
            )
            return
        for category in self.categories:
            self._values[category.slug] = self._read_category(category)

    def _prepare_profile(self) -> bool:
        """Создаёт папки профиля; False — профиль недоступен (read-only)."""
        if self._fm is None:
            return False
        try:
            self._fm.create_dir(SETTINGS_DIR)
            self._fm.create_dir(PLUGINS_DIR)
            self._readonly = False
        except (OSError, ValueError, NotImplementedError) as exc:
            self._readonly = True
            logger.error("SettingsStore: cannot use profile storage: %s", exc)
        return not self._readonly

    def _read_category(self, category: Category) -> dict[str, Any]:
        """Значения категории: умолчания, поверх — файл профиля."""
        result = dict(self._defaults[category.slug])
        stored = self._stored(category)
        if stored:
            logger.info("SettingsStore: %s overridden by %d keys", category.slug, len(stored))
        for spec in category.settings:
            if spec.key in stored:
                result[spec.key] = ValueCodec.from_json(spec, stored[spec.key])
        return result

    def _stored(self, category: Category) -> dict[str, Any]:
        """Сырой JSON-словарь значений категории (пусто — файла нет)."""
        if self._fm is None:
            return {}
        relative = self.path_for(category)
        if not self._fm.exists(relative):
            return {}
        try:
            payload = json.loads(self._fm.read_text(relative))
        except (OSError, ValueError) as exc:
            logger.error("SettingsStore: cannot read %s: %s", relative, exc)
            return {}
        if not isinstance(payload, dict):
            logger.error("SettingsStore: %s must contain a JSON object", relative)
            return {}
        return payload

    def _persist(self, category: Category, payload: dict[str, Any]) -> None:
        """Пишет JSON-словарь значений категории в профиль."""
        if self._readonly:
            raise SettingsError(
                "user profile is not writable; settings cannot be saved"
            )
        relative = self.path_for(category)
        if not payload:
            if self._fm.exists(relative):
                self._fm.delete(relative)
            return
        text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
        self._fm.write_text(relative, f"{text}\n")

    def _current(self, category: Category, spec: SettingSpec) -> Any:
        """Текущее эффективное значение настройки (dirty-правка, иначе файл/умолчание)."""
        return self._values[category.slug][spec.key]

    def _known_keys(self) -> set[str]:
        """Все полные ключи текущей схемы (фильтр для восстановленных правок)."""
        return {
            f"{category.slug}.{spec.key}"
            for category in self.categories
            for spec in category.settings
        }

    def _notify(self) -> None:
        """Сообщает подписчикам об изменении значений."""
        for listener in self._listeners:
            listener()

    def _notify_changed(self, slug: str, key: str) -> None:
        """Сообщает об изменении конкретной настройки (для applier'ов)."""
        for listener in self._change_listeners:
            listener(slug, key)