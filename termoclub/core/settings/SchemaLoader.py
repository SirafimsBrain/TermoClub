# termoclub/core/settings/SchemaLoader.py
"""Загрузка схемы настроек из JSON-файлов.

Встроенная схема лежит в составе приложения
(`core/settings/schema/*.json` и `core/settings/schema/plugins/*.json`) —
это «умолчания» приложения. Плагинные схемы могут доставляться и из
папок плагинов: их читает `PluginSettingsScanner`, собирая те же
`Category`, поэтому загрузчик умеет разбирать и одиночный файл.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core.settings.Category import Category
from core.settings.SettingsError import SettingsError
from core.settings.SettingsSchema import SettingsSchema

logger = logging.getLogger(__name__)

#: Папка со встроенной схемой (рядом с пакетом настроек).
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"


class SchemaLoader:
    """Читает JSON-схему и превращает её в `SettingsSchema`."""

    def __init__(self, schema_dir: Path | str | None = None) -> None:
        self._dir = Path(schema_dir) if schema_dir is not None else SCHEMA_DIR

    @property
    def directory(self) -> Path:
        """Папка со встроенными файлами схемы."""
        return self._dir

    def load_app_schema(self) -> SettingsSchema:
        """Загружает категории приложения и встроенные схемы плагинов."""
        schema = SettingsSchema(self._load_dir(self._dir))
        plugin_dir = self._dir / "plugins"
        for category in self._load_dir(plugin_dir):
            schema.add(category)
        logger.info(
            "SchemaLoader: loaded %d categories (%d plugin)",
            len(schema.categories),
            len(schema.plugin_categories),
        )
        return schema

    def load_category(self, path: Path | str, *, plugin: str = "") -> Category:
        """Загружает одну категорию из файла (схема плагина с диска)."""
        return self._read(Path(path), plugin=plugin)

    def _load_dir(self, directory: Path) -> list[Category]:
        """Читает все `*.json` директории; битый файл не роняет загрузку."""
        if not directory.is_dir():
            logger.warning("SchemaLoader: no schema directory %s", directory)
            return []
        categories: list[Category] = []
        for path in sorted(directory.glob("*.json")):
            plugin = path.parent.name == "plugins" and path.stem or ""
            try:
                categories.append(self._read(path, plugin=plugin))
            except (SettingsError, ValueError, OSError) as exc:
                logger.error("SchemaLoader: skipping %s: %s", path.name, exc)
        return categories

    def _read(self, path: Path, *, plugin: str = "") -> Category:
        """Читает и разбирает один файл схемы."""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SettingsError(f"{path.name}: invalid JSON: {exc}") from None
        try:
            return Category.from_dict(payload, plugin=plugin)
        except ValueError as exc:
            raise SettingsError(f"{path.name}: {exc}") from None