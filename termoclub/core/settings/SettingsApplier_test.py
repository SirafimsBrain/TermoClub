# termoclub/core/settings/SettingsApplier_test.py
"""Тесты применения настроек к живым частям приложения.

`SettingsApplier` — мост от хранилища к тому, что уже работает: тема окна,
уровень логирования, активный терминал, внешний вид вкладок терминала.
Проверяется, что обработчики вызываются по имени из схемы и что сбой
одной настройки не мешает остальным.
"""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest

from core.result import Result
from core.settings.SettingsApplier import SettingsApplier
from core.settings.SettingsStore import SettingsStore
from core.storage.backends.ProfileBackend import ProfileBackend
from core.storage.FileManager import FileManager


class _StubSession:
    """Сессия терминала с минимальным контрактом applier'а."""

    def __init__(self, category: str) -> None:
        self.appearance_category = category
        self.appearance: list[dict] = []
        self.rates: list[int] = []

    def apply_appearance(self, appearance: dict) -> None:
        self.appearance.append(appearance)

    def apply_refresh_rate(self, per_second: int) -> None:
        self.rates.append(per_second)


class _StubTerminal:
    def __init__(self) -> None:
        self.focused = 0

    def focus(self) -> Result:
        self.focused += 1
        return Result(True, "focused")


class _StubPage:
    def __init__(self) -> None:
        self.theme = SimpleNamespace(color_scheme_seed="#2196f3")
        self.theme_mode = ft.ThemeMode.DARK
        self.updates = 0

    def update(self) -> None:
        self.updates += 1


def _store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(FileManager(ProfileBackend(tmp_path / ".termoclub")))


def _applier(tmp_path: Path, sessions=None, page=None, terminal=None) -> SettingsApplier:
    store = _store(tmp_path)
    applier = SettingsApplier(
        store,
        sessions=(lambda: sessions) if sessions is not None else None,
        page=page,
        terminal_factory=(lambda _name: terminal) if terminal is not None else None,
    )
    return applier


def test_theme_mode_and_seed_reach_the_page(tmp_path: Path) -> None:
    """Тема и её базовый цвет применяются к странице."""
    page = _StubPage()
    applier = _applier(tmp_path, page=page)
    applier.apply_spec("global", "theme_mode", "theme_mode")
    applier.apply_spec("appearance", "theme_seed", "theme_seed")

    assert page.theme_mode is ft.ThemeMode.DARK
    assert page.theme.color_scheme_seed == "#2196f3"
    assert page.updates == 2


def test_log_level_changes_root_logger(tmp_path: Path) -> None:
    """Уровень логирования из настроек меняет корневой логгер."""
    applier = _applier(tmp_path)
    previous = logging.getLogger().level
    try:
        assert applier.apply_spec("global", "log_level", "log_level")
        assert logging.getLogger().level == logging.INFO
    finally:
        logging.getLogger().setLevel(previous)


def test_terminal_appearance_only_touches_matching_category(tmp_path: Path) -> None:
    """Внешний вид применяется только к вкладкам своей категории."""
    pyte = _StubSession("terminal-pyte")
    gpu = _StubSession("terminal-smartcli")
    applier = _applier(tmp_path, sessions=[pyte, gpu])

    assert applier.apply_spec("terminal-pyte", "font_size", "terminal_appearance")
    assert pyte.appearance and not gpu.appearance
    assert pyte.appearance[0]["font_size"] == 13


def test_refresh_rate_reaches_matching_terminals_only(tmp_path: Path) -> None:
    """Частота перерисовки меняется у вкладок своей категории."""
    pyte = _StubSession("terminal-pyte")
    gpu = _StubSession("terminal-smartcli")
    applier = _applier(tmp_path, sessions=[pyte, gpu])

    assert applier.apply_spec("terminal-pyte", "refresh_rate", "terminal_refresh")
    assert pyte.rates == [20] and gpu.rates == []

    assert applier.apply_spec("terminal-smartcli", "font_size", "terminal_appearance")
    assert gpu.appearance and pyte.appearance == []


def test_active_terminal_is_focused_through_factory(tmp_path: Path) -> None:
    """Активный внешний терминал запрашивает фокус у контроллера."""
    terminal = _StubTerminal()
    applier = _applier(tmp_path, terminal=terminal)
    assert applier.apply_spec("external-tools", "active_terminal", "active_terminal")
    assert terminal.focused == 1


def test_apply_all_covers_every_spec_with_applier(tmp_path: Path) -> None:
    """`apply_all` обходит все настройки со `applier` в схеме."""
    applier = _applier(tmp_path, sessions=[])
    applied = applier.apply_all()
    expected = {
        f"{category.slug}.{spec.key}"
        for category in applier._store.categories
        for spec in category.settings
        if spec.applier
    }
    assert set(applied) == expected


def test_unknown_applier_is_reported_not_raised(tmp_path: Path) -> None:
    """Неизвестный applier — это `False` в логе, а не исключение."""
    applier = _applier(tmp_path)
    assert applier.apply_spec("global", "theme_mode", "no-such-applier") is False


def test_apply_key_takes_applier_name_from_schema(tmp_path: Path) -> None:
    """`apply_key` берёт имя обработчика из схемы (вход для подписки)."""
    page = _StubPage()
    applier = _applier(tmp_path, page=page)
    assert applier.apply_key("global", "theme_mode") is True
    assert applier.apply_key("global", "shell") is False  # у настройки нет applier'а
    assert applier.apply_key("no-such-category", "theme_mode") is False


def test_failing_handler_does_not_break_the_rest(tmp_path: Path) -> None:
    """Падение обработчика логируется, но не роняет применение настроек."""

    class Boom:
        @property
        def theme_mode(self) -> str:
            raise RuntimeError("boom")

        @theme_mode.setter
        def theme_mode(self, value: str) -> None:
            raise RuntimeError("boom")

    applier = _applier(tmp_path, page=Boom())
    assert applier.apply_spec("global", "theme_mode", "theme_mode") is False
    assert applier.apply_key("global", "log_level") is True


# --- Пределы ширины боковых панелей ---


def test_panel_limits_reach_the_layout(tmp_path: Path) -> None:
    """Пределы ширины панелей уходят в UI-слой одним сообщением.

    Оба предела передаются вместе: панели должны быть в согласованном
    состоянии после правки любой из двух настроек.
    """
    seen: list[tuple[int, int]] = []
    store = _store(tmp_path)
    applier = SettingsApplier(store)
    applier.register_panel_limits(lambda left, right: seen.append((left, right)))

    store.set("appearance", "left_panel_max_width", 480)
    applier.apply_key("appearance", "left_panel_max_width")
    assert seen[-1] == (480, 600)

    store.set("appearance", "right_panel_max_width", 700)
    applier.apply_key("appearance", "right_panel_max_width")
    assert seen[-1] == (480, 700)


def test_panel_limits_survive_a_missing_schema_key(tmp_path: Path) -> None:
    """Если настройки в схеме нет, предел берётся по умолчанию.

    Схему плагина или старый профиль менять нельзя, а панель всё равно
    должна получить работоспособный предел.
    """
    seen: list[tuple[int, int]] = []
    store = _store(tmp_path)
    applier = SettingsApplier(store)
    applier.register_panel_limits(lambda left, right: seen.append((left, right)))

    applier.apply_spec("appearance", "left_panel_max_width", "panel_widths")
    assert seen[-1] == (600, 600)


def test_panel_widths_without_a_target_are_ignored(tmp_path: Path) -> None:
    """Пока UI не зарегистрировал приёмник, обработчик молча выходит."""
    applier = _applier(tmp_path)
    assert applier.apply_key("appearance", "left_panel_max_width") is True