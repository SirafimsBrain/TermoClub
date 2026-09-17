# termoclub/core/settings/PluginScanning_test.py
"""Тесты сканирования плагинов: их схемы и динамические варианты выбора.

Плагин — папка в `~/.termoclub/plugins`. Приложение само находит её,
подхватывает `settings.json` как категорию, пишет значения в `values.json`
этого плагина и наполняет список `plugins.disabled_plugins` именами
найденных плагинов.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.settings.PluginSettingsScanner import MANIFEST_FILE, SCHEMA_FILE
from core.settings.SettingsScope import SettingsScope
from core.settings.SettingsStore import PLUGINS_DIR, PLUGIN_VALUES_FILE, SettingsStore
from core.storage.backends.ProfileBackend import ProfileBackend
from core.storage.FileManager import FileManager

PLUGIN_SCHEMA = {
    "slug": "demo-plugin",
    "title": "Demo",
    "order": 910,
    "settings": {
        "greeting": {"type": "string", "label": "Greeting", "default": "hi"},
        "verbose": {"type": "boolean", "label": "Verbose", "default": False},
    },
}


def _plugin(profile: Path, name: str = "demo", schema: dict | None = None) -> Path:
    """Создаёт папку плагина со схемой настроек (и манифестом)."""
    path = profile / PLUGINS_DIR / name
    path.mkdir(parents=True)
    (path / SCHEMA_FILE).write_text(json.dumps(schema or PLUGIN_SCHEMA), encoding="utf-8")
    (path / MANIFEST_FILE).write_text(
        json.dumps({"title": "Demo Plugin", "version": "1.2.3", "order": 910}),
        encoding="utf-8",
    )
    return path


def _store(profile: Path) -> SettingsStore:
    return SettingsStore(FileManager(ProfileBackend(profile)))


def test_plugin_category_appears_after_scan(tmp_path: Path) -> None:
    """Категория плагина появляется в схеме после сканирования."""
    profile = tmp_path / ".termoclub"
    _plugin(profile)
    store = _store(profile)
    assert store.schema.find("demo-plugin") is None

    found = store.refresh_plugins()
    assert [plugin.name for plugin in found] == ["demo"]
    category = store.schema.find("demo-plugin")
    assert category is not None
    assert category.scope is SettingsScope.PLUGIN
    assert category.plugin == "demo"
    assert category.title == "Demo Plugin"
    assert category in store.schema.plugin_categories


def test_plugin_values_are_stored_next_to_the_plugin(tmp_path: Path) -> None:
    """Значения плагина пишутся в его собственный `values.json`."""
    profile = tmp_path / ".termoclub"
    _plugin(profile)
    store = _store(profile)
    store.refresh_plugins()
    store.set("demo-plugin", "greeting", "hello", save=True)

    values_file = profile / PLUGINS_DIR / "demo" / PLUGIN_VALUES_FILE
    assert json.loads(values_file.read_text(encoding="utf-8")) == {"greeting": "hello"}

    fresh = _store(profile)
    fresh.refresh_plugins()
    assert fresh.get("demo-plugin", "greeting") == "hello"


def test_disabled_plugins_choices_are_filled_by_scanner(tmp_path: Path) -> None:
    """Список отключаемых плагинов наполняется именами найденных папок."""
    profile = tmp_path / ".termoclub"
    _plugin(profile, "one", {**PLUGIN_SCHEMA, "slug": "one-plugin"})
    _plugin(profile, "two", {**PLUGIN_SCHEMA, "slug": "two-plugin"})
    store = _store(profile)
    assert store.schema.require("plugins").spec("disabled_plugins").choices == []

    store.refresh_plugins()
    # Схема после пересканирования пересобирается, поэтому категорию берём заново.
    choices = store.schema.require("plugins").spec("disabled_plugins").choices
    assert [c.value for c in choices] == ["one", "two"]


def test_disabled_plugin_schema_is_not_loaded(tmp_path: Path) -> None:
    """Отключённый плагин виден в списке, но его настроек в схеме нет."""
    profile = tmp_path / ".termoclub"
    (profile / "settings").mkdir(parents=True)
    _plugin(profile)
    (profile / "settings" / "plugins.json").write_text(
        json.dumps({"disabled_plugins": ["demo"]}), encoding="utf-8"
    )
    store = _store(profile)
    store.refresh_plugins()

    found = {plugin.name: plugin for plugin in store.refresh_plugins()}
    assert found["demo"].enabled is False
    assert store.schema.find("demo-plugin") is None


def test_scan_reports_problems_of_broken_plugins(tmp_path: Path) -> None:
    """Плагин без схемы и с битым манифестом попадает в отчёт сканера."""
    profile = tmp_path / ".termoclub"
    empty = profile / PLUGINS_DIR / "noschema"
    empty.mkdir(parents=True)
    broken = _plugin(profile, "broken")
    (broken / MANIFEST_FILE).write_text("{oops", encoding="utf-8")

    store = _store(profile)
    found = {plugin.name: plugin for plugin in store.refresh_plugins()}
    assert found["noschema"].has_settings is False
    assert any("settings.json" in problem for problem in found["noschema"].problems)
    assert any(MANIFEST_FILE in problem for problem in found["broken"].problems)
    assert found["broken"].has_settings is True


def test_plugin_directory_setting_selects_the_folder(tmp_path: Path) -> None:
    """`plugins.plugin_directory` задаёт папку сканирования вместо профиля."""
    profile = tmp_path / ".termoclub"
    store = _store(profile)
    _plugin(profile)  # плагин в папке по умолчанию
    moved = profile / "extra-plugins" / "demo"
    moved.parent.mkdir()
    (profile / PLUGINS_DIR / "demo").rename(moved)

    store.set("plugins", "plugin_directory", "extra-plugins")
    assert [plugin.name for plugin in store.refresh_plugins()] == ["demo"]


def test_absolute_plugin_directory_falls_back_to_the_profile(tmp_path: Path) -> None:
    """Абсолютный путь отвергается: `FileManager` работает внутри профиля."""
    profile = tmp_path / ".termoclub"
    store = _store(profile)
    store.set("plugins", "plugin_directory", str(tmp_path / "elsewhere"))
    _plugin(profile)

    assert [plugin.name for plugin in store.refresh_plugins()] == ["demo"]