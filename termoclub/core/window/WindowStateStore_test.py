# termoclub/core/window/WindowStateStore_test.py
"""Тесты посредника состояния окна: файл профиля, умолчания, read-only."""
from __future__ import annotations

import json

import pytest

from core.storage.FileManager import FileManager
from core.storage.backends.ProfileBackend import ProfileBackend
from core.window.WindowState import DEFAULT_HEIGHT, DEFAULT_WIDTH, WindowState
from core.window.WindowStateStore import STATE_FILE, WindowStateStore


@pytest.fixture
def fm(tmp_path):
    """Настоящий `FileManager` поверх временного профиля."""
    return FileManager(ProfileBackend(tmp_path))


def test_first_run_returns_defaults_and_writes_nothing(fm) -> None:
    """Пока состояния нет, отдаём умолчания и файл не создаём."""
    store = WindowStateStore(fm)
    assert store.state == WindowState()
    assert not fm.exists(STATE_FILE)


def test_update_alone_does_not_touch_the_disk(fm) -> None:
    """По умолчанию `update` пишет только в память.

    Состояние окна сохраняется один раз, при закрытии приложения: частые
    записи изнашивают SSD. Здесь это и проверяется — файла нет.
    """
    store = WindowStateStore(fm)
    store.update(width=1600, height=1000, left_panel_open=True)

    assert store.state.width == 1600
    assert not fm.exists(STATE_FILE)


def test_save_writes_the_profile_file(fm) -> None:
    """Явное сохранение доводит состояние до файла профиля."""
    store = WindowStateStore(fm)
    store.update(width=1600, height=1000, left_panel_open=True)
    assert store.save() is True

    payload = json.loads(fm.read_text(STATE_FILE))
    assert payload["width"] == 1600
    assert payload["left_panel_open"] is True
    assert payload["right_panel_open"] is False


def test_state_survives_a_restart(fm) -> None:
    """Сохранённое состояние читается новым посредником (перезапуск)."""
    store = WindowStateStore(fm)
    store.update(width=1024, height=768, right_panel_open=True)
    store.save()

    restored = WindowStateStore(fm).state
    assert (restored.width, restored.height) == (1024, 768)
    assert restored.right_panel_open is True
    assert restored.left_panel_open is False


def test_panels_toggle_is_persisted_independently(fm) -> None:
    """Панели хранятся раздельно: раскрытие одной не меняет другую."""
    store = WindowStateStore(fm)
    store.update(left_panel_open=True)
    store.update(right_panel_open=True)
    store.update(left_panel_open=False)
    store.save()

    restored = WindowStateStore(fm).state
    assert (restored.left_panel_open, restored.right_panel_open) == (False, True)


def test_corrupt_file_falls_back_to_defaults(fm) -> None:
    """Испорченный файл не роняет запуск: берём умолчания."""
    fm.write_text(STATE_FILE, "{not json at all")
    store = WindowStateStore(fm)
    assert store.state == WindowState()


def test_unknown_field_is_rejected(fm) -> None:
    """Опечатка в имени поля — явная ошибка, а не тихая запись мусора."""
    store = WindowStateStore(fm)
    with pytest.raises(AttributeError):
        store.update(nosuchfield=1)


def test_explicit_save_on_update_writes_immediately(fm) -> None:
    """`save=True` — путь для случаев, когда запись нужна сразу."""
    store = WindowStateStore(fm)
    store.update(width=1600, save=True)
    assert json.loads(fm.read_text(STATE_FILE))["width"] == 1600


def test_reset_returns_defaults_and_saves(fm) -> None:
    """Сброс вида возвращает умолчания и фиксирует их в файле."""
    store = WindowStateStore(fm)
    store.update(width=1600, left_panel_open=True)
    store.save()

    store.reset()
    assert store.state == WindowState()
    assert json.loads(fm.read_text(STATE_FILE))["width"] == DEFAULT_WIDTH


def test_unavailable_profile_is_read_only(monkeypatch) -> None:
    """Без профиля store работает только на чтение и не падает.

    Профиль недоступен, когда `FileManager` не может открыть корень — это и
    воспроизводим, а не подменяем внутренние поля объекта.
    """

    def _explode(self, backend=None):  # type: ignore[no-untyped-def]
        raise OSError("no profile")

    monkeypatch.setattr(FileManager, "__init__", _explode)

    store = WindowStateStore()
    assert store.readonly is True
    assert store.state == WindowState()
    assert store.save() is False


def test_empty_payload_uses_defaults(fm) -> None:
    """Пустой JSON-объект даёт полностью умолчательные значения."""
    fm.write_text(STATE_FILE, "{}")
    state = WindowStateStore(fm).state
    assert (state.width, state.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    assert (state.left_panel_open, state.right_panel_open) == (False, False)


# --- Ширина панелей ---


def test_panel_widths_survive_a_restart(fm) -> None:
    """Ширина панелей, выставленная мышью, переживает перезапуск."""
    store = WindowStateStore(fm)
    store.update(left_panel_width=340, right_panel_width=420)
    store.save()

    restored = WindowStateStore(fm).state
    assert (restored.left_panel_width, restored.right_panel_width) == (340, 420)


def test_panel_widths_are_not_written_before_close(fm) -> None:
    """Тяга панели пишет только в память: файла до закрытия нет."""
    store = WindowStateStore(fm)
    store.update(left_panel_width=340)
    assert store.state.left_panel_width == 340
    assert not fm.exists(STATE_FILE)


def test_absent_panel_width_means_unset(fm) -> None:
    """Без сохранённой ширины панель открывается по умолчанию (0 — не задано)."""
    fm.write_text(STATE_FILE, "{}")
    state = WindowStateStore(fm).state
    assert (state.left_panel_width, state.right_panel_width) == (0, 0)


def test_broken_panel_width_falls_back_to_default(fm) -> None:
    """Мусор в поле ширины не роняет запуск: панель берёт умолчание."""
    fm.write_text(
        STATE_FILE,
        json.dumps({"left_panel_width": "wide", "right_panel_width": None}),
    )
    state = WindowStateStore(fm).state
    assert (state.left_panel_width, state.right_panel_width) == (0, 0)


def test_negative_panel_width_is_treated_as_unset(fm) -> None:
    """Отрицательная ширина бессмысленна — читается как «не задана»."""
    fm.write_text(STATE_FILE, json.dumps({"left_panel_width": -50}))
    assert WindowStateStore(fm).state.left_panel_width == 0