# termoclub/core/settings/SettingsLayers_test.py
"""Тесты слоёв настроек: встроенные умолчания и профиль пользователя.

Главное, что проверяется, — приоритет: файлы профиля перекрывают
встроенную схему, а если профиль недоступен, приложение работает на
встроенных умолчаниях в режиме «только чтение».
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.settings.SettingsError import SettingsError
from core.settings.SettingsStore import SETTINGS_DIR, SettingsStore
from core.storage.backends.ProfileBackend import ProfileBackend
from core.storage.FileManager import FileManager


def _store(tmp_path: Path) -> SettingsStore:
    """Хранилище поверх временного профиля (без реального `~/.termoclub`)."""
    return SettingsStore(FileManager(ProfileBackend(tmp_path / ".termoclub")))


def test_defaults_come_from_builtin_schema(tmp_path: Path) -> None:
    """Без файлов профиля значения берутся из встроенной схемы."""
    store = _store(tmp_path)
    assert store.get("global", "theme_mode") == "dark"
    assert store.get("terminal-pyte", "font_size") == 13
    assert store.modified() == []


def test_profile_overrides_builtin_defaults(tmp_path: Path) -> None:
    """Значения из файла профиля приоритетнее встроенных умолчаний."""
    profile = tmp_path / ".termoclub"
    (profile / SETTINGS_DIR).mkdir(parents=True)
    (profile / SETTINGS_DIR / "global.json").write_text(
        json.dumps({"theme_mode": "light"}), encoding="utf-8"
    )
    store = _store(tmp_path)
    assert store.get("global", "theme_mode") == "light"
    assert store.get("global", "log_level") == "INFO"
    assert store.is_modified("global", "theme_mode")
    assert "global.theme_mode" in store.modified()


def test_set_writes_only_differences_and_reload_sees_them(tmp_path: Path) -> None:
    """Сохранение пишет только отличия от умолчаний, перечитывание их видит."""
    store = _store(tmp_path)
    store.set("terminal-pyte", "font_size", 18, save=True)
    payload = json.loads(
        (tmp_path / ".termoclub" / SETTINGS_DIR / "terminal-pyte.json").read_text()
    )
    assert payload == {"font_size": 18}

    fresh = _store(tmp_path)
    assert fresh.get("terminal-pyte", "font_size") == 18
    assert fresh.get("terminal-pyte", "padding") == 8


def test_reset_removes_key_from_profile_file(tmp_path: Path) -> None:
    """Сброс настройки убирает её из файла профиля."""
    store = _store(tmp_path)
    store.set("global", "log_level", "DEBUG", save=True)
    store.reset("global", "log_level", save=True)
    path = tmp_path / ".termoclub" / SETTINGS_DIR / "global.json"
    assert not path.exists()
    assert store.get("global", "log_level") == "INFO"


def test_reset_category_deletes_its_file(tmp_path: Path) -> None:
    """Сброс категории удаляет файл целиком."""
    store = _store(tmp_path)
    store.set("global", "log_level", "DEBUG")
    store.set("global", "confirm_on_exit", False)
    store.save_category("global")
    assert (tmp_path / ".termoclub" / SETTINGS_DIR / "global.json").exists()

    store.reset_category("global")
    assert not (tmp_path / ".termoclub" / SETTINGS_DIR / "global.json").exists()
    assert store.get("global", "log_level") == "INFO"


def test_broken_json_falls_back_to_defaults(tmp_path: Path) -> None:
    """Битый JSON профиля не роняет приложение: берутся умолчания."""
    profile = tmp_path / ".termoclub" / SETTINGS_DIR
    profile.mkdir(parents=True)
    (profile / "global.json").write_text("{not json", encoding="utf-8")
    store = _store(tmp_path)
    assert store.get("global", "theme_mode") == "dark"


def test_unknown_values_in_profile_fall_back_to_defaults(tmp_path: Path) -> None:
    """Чужой вариант выбора и неверный тип откатываются к умолчанию."""
    profile = tmp_path / ".termoclub" / SETTINGS_DIR
    profile.mkdir(parents=True)
    (profile / "global.json").write_text(
        json.dumps({"theme_mode": "neon", "session_limit": "many"}),
        encoding="utf-8",
    )
    store = _store(tmp_path)
    assert store.get("global", "theme_mode") == "dark"
    assert store.get("global", "session_limit") == 10


def test_readonly_store_rejects_writes(tmp_path: Path) -> None:
    """Недоступный профиль переводит хранилище в режим «только чтение»."""
    store = _store(tmp_path)
    store._readonly = True  # имитация: домашний каталог недоступен для записи
    assert store.get("global", "theme_mode") == "dark"
    with pytest.raises(SettingsError):
        store.set("global", "theme_mode", "light")


def test_change_subscribers_receive_slug_and_key(tmp_path: Path) -> None:
    """Подписчики получают пары `slug/key` — ими пользуется applier."""
    store = _store(tmp_path)
    seen: list[tuple[str, str]] = []
    store.subscribe_changes(lambda slug, key: seen.append((slug, key)))
    store.set("terminal-pyte", "font_size", 20)
    store.reset("terminal-pyte", "font_size")
    assert seen == [
        ("terminal-pyte", "font_size"),
        ("terminal-pyte", "font_size"),
    ]


def test_values_and_all_values_return_types_from_schema(tmp_path: Path) -> None:
    """`values`/`all_values` отдают значения категорий и всех категорий."""
    store = _store(tmp_path)
    store.set("global", "update_check_date", "2026-01-31")
    values = store.values("global")
    assert values["update_check_date"].isoformat() == "2026-01-31"
    assert values["theme_mode"] == "dark"
    assert set(store.all_values()) == {c.slug for c in store.categories}


def test_find_matches_key_title_and_description(tmp_path: Path) -> None:
    """Поиск по настройкам ищет по ключу, подписи, описанию и категории."""
    store = _store(tmp_path)
    assert [spec.key for _cat, spec in store.find("scrollback")] == ["scrollback"]
    assert {cat.slug for cat, _spec in store.find("terminal")} >= {
        "terminal-pyte",
        "terminal-smartcli",
    }
    assert store.find("   ") == []