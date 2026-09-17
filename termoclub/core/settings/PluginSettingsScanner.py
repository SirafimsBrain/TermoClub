# termoclub/core/settings/PluginSettingsScanner.py
"""Сканирование папок плагинов и подхват их настроек.

Плагин — папка внутри `~/.termoclub/plugins/<имя>/`. Приложение само
находит их и, если рядом лежит схема настроек (`settings.json`), строит
для плагина категорию с теми же типами значений, что и у встроенных
разделов. Значения плагин хранит в своём файле (`values.json`).

Итог работы сканера — новый `SettingsSchema`, куда добавлены категории
плагинов, и список `PluginInfo` для GUI.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core.settings.PluginInfo import PluginInfo
from core.settings.SchemaLoader import SchemaLoader
from core.settings.SettingsError import SettingsError
from core.settings.SettingsSchema import SettingsSchema
from core.storage.FileManager import FileManager

logger = logging.getLogger(__name__)

#: Папка плагинов внутри профиля.
PLUGINS_DIR = "plugins"

#: Файл манифеста плагина (необязателен).
MANIFEST_FILE = "plugin.json"

#: Файл схемы настроек плагина.
SCHEMA_FILE = "settings.json"

#: Максимальная глубина обхода в поисках папки со схемой настроек.
MAX_DEPTH = 3


class PluginSettingsScanner:
    """Находит плагины в профиле и добавляет их настройки в схему."""

    def __init__(
        self,
        file_manager: FileManager | None = None,
        loader: SchemaLoader | None = None,
        directory: str | Path | None = None,
    ) -> None:
        self._fm = file_manager or FileManager()
        self._loader = loader or SchemaLoader()
        self._directory = Path(directory) if directory is not None else Path(PLUGINS_DIR)
        self._plugins: list[PluginInfo] = []

    @property
    def plugins(self) -> list[PluginInfo]:
        """Плагины, найденные последним сканированием."""
        return list(self._plugins)

    def scan(self, schema: SettingsSchema, disabled: set[str] | None = None) -> SettingsSchema:
        """Дочитывает категории плагинов в схему и возвращает её же."""
        disabled = disabled or set()
        self._plugins = []
        for name, path in self._candidate_dirs():
            info = self._describe(name, path, disabled)
            self._plugins.append(info)
            if not info.has_settings or not info.enabled:
                continue
            try:
                category = self._loader.load_category(
                    path / info.settings_file, plugin=name
                )
            except (SettingsError, ValueError, OSError) as exc:
                info.problems.append(str(exc))
                logger.error("PluginSettingsScanner: %s: %s", name, exc)
                continue
            category.title = info.title or category.title
            category.icon = info.icon or category.icon
            category.description = info.description or category.description
            category.order = info.order
            schema.replace(category)
            logger.info("PluginSettingsScanner: settings of %r added", name)
        logger.info(
            "PluginSettingsScanner: %d plugins, %d with settings",
            len(self._plugins),
            sum(1 for p in self._plugins if p.has_settings),
        )
        return schema

    def names(self) -> list[str]:
        """Имена найденных плагинов (для настройки «отключённые плагины»)."""
        return [plugin.name for plugin in self._plugins]

    def _candidate_dirs(self) -> list[tuple[str, Path]]:
        """Папки верхнего уровня внутри каталога плагинов.

        `FileManager` — обёртка над профилем, но сканер обязан работать и с
        произвольным каталогом, поэтому имена берутся из файловой системы,
        а чтение файлов идёт через `FileManager` (относительные пути).
        """
        root = self._fm.root / self._directory
        if not root.is_dir():
            logger.info("PluginSettingsScanner: no plugin directory %s", root)
            return []
        found: list[tuple[str, Path]] = []
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                found.append((entry.name, entry))
        return found

    def _describe(self, name: str, path: Path, disabled: set[str]) -> PluginInfo:
        """Собирает сведения о плагине: манифест и наличие схемы настроек."""
        info = PluginInfo(name=name, enabled=name not in disabled, path=path)
        manifest = path / MANIFEST_FILE
        if manifest.is_file():
            self._apply_manifest(info, manifest)
        settings_file = self._find_settings(path)
        if settings_file is not None:
            info.has_settings = True
            info.settings_file = settings_file.name
        else:
            info.problems.append(f"no {SCHEMA_FILE} found")
            logger.warning("PluginSettingsScanner: %s has no settings schema", name)
        return info

    def _apply_manifest(self, info: PluginInfo, manifest: Path) -> None:
        """Читает необязательный манифест плагина (ошибки — в problems)."""
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            info.problems.append(f"{MANIFEST_FILE}: {exc}")
            logger.error("PluginSettingsScanner: %s: %s", manifest, exc)
            return
        if not isinstance(payload, dict):
            info.problems.append(f"{MANIFEST_FILE}: expected an object")
            return
        info.title = _text(payload.get("title"), info.title)
        info.version = _text(payload.get("version"), "")
        info.description = _text(payload.get("description"), "")
        info.icon = _text(payload.get("icon"), info.icon)
        order = payload.get("order")
        if isinstance(order, (int, float)) and not isinstance(order, bool):
            info.order = int(order)

    def _find_settings(self, path: Path) -> Path | None:
        """Ищет файл схемы настроек в папке плагина (до `MAX_DEPTH` уровней)."""
        direct = path / SCHEMA_FILE
        if direct.is_file():
            return direct
        root_depth = len(path.parts)
        for candidate in sorted(path.rglob(SCHEMA_FILE)):
            if len(candidate.parts) - root_depth <= MAX_DEPTH:
                return candidate
        return None


def _text(value: object, fallback: str) -> str:
    """Строковое поле манифеста."""
    return value if isinstance(value, str) and value else fallback