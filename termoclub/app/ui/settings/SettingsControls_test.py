# termoclub/app/ui/settings/SettingsControls_test.py
"""Тесты GUI-слоя настроек: виджеты, панель и вкладка.

Проверяется главное: каждый тип значения схемы получает свой виджет, а
изменение виджета доходит до хранилища (и до файла профиля) — и наоборот,
значение из хранилища попадает в виджет. Flet-страница подменяется
заглушкой: приложение в тестах не запускается.
"""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest

from app.pages.settings import DEFAULT_CATEGORY, SettingsPage, SettingsSession
from app.ui.flet_contract import check_control
from app.ui.settings.BooleanSettingControl import BooleanSettingControl
from app.ui.settings.ChoiceSettingControl import (
    EMPTY_CHOICES_TEXT,
    ChoiceSettingControl,
    MultiChoiceSettingControl,
)
from app.ui.settings.ColorSettingControl import ColorSettingControl
from app.ui.settings.DateTimeSettingControl import DateTimeSettingControl
from app.ui.settings.LinkOpener import LinkOpener
from app.ui.settings.LinkSettingControl import LinkSettingControl
from app.ui.settings.NumberSettingControl import NumberSettingControl
from app.ui.settings.PathPicker import PathPicker
from app.ui.settings.PathSettingControl import PathSettingControl
from app.ui.settings.SettingControl import TEXT_MIN_WIDTH, SettingControl
from app.ui.settings.SettingsControls import SettingsControls
from app.ui.settings.SettingsDeps import SettingsDeps
from app.ui.settings.TextSettingControl import TextSettingControl
from core.settings.Category import Category
from core.settings.SettingsStore import SETTINGS_DIR, SettingsStore
from core.settings.ValueType import ValueType
from core.storage.backends.ProfileBackend import ProfileBackend
from core.storage.FileManager import FileManager


class _StubPage:
    """Минимальная страница Flet: сервисы, диалоги, добавление контролов.

    У реального `ft.Page` нет атрибута `dialogs`: диалоги живут во внутреннем
    стеке, а наружу торчит только `show_dialog(DialogControl)`. Поэтому
    заглушка записывает то, что получил `show_dialog`, и тесты проверяют
    именно этот контракт — что контрол является `ft.DialogControl`.
    """

    def __init__(self) -> None:
        self.fonts: dict | None = None
        self.services: list = []
        self.shown_dialogs: list = []

    def update(self) -> None:
        pass

    def run_task(self, handler, *args):  # type: ignore[no-untyped-def]
        return None

    def show_dialog(self, dialog) -> None:  # type: ignore[no-untyped-def]
        self.shown_dialogs.append(dialog)


def _store(tmp_path: Path, autosave: bool = False, extra: dict | None = None) -> SettingsStore:
    """Хранилище поверх временного профиля, при необходимости с лишней категорией.

    Дополнительная категория нужна там, где проверяется виджет для типа
    значения, которого нет во встроенной схеме (`datetime`, `multi_choice`
    с длинным списком): схема остаётся единственным источником правды.
    """
    fm = FileManager(ProfileBackend(tmp_path / ".termoclub"))
    if extra is None:
        store = SettingsStore(fm)
    else:
        schema = SettingsStore(fm).schema
        schema.add(Category.from_dict(extra))
        store = SettingsStore(fm, schema=schema)
    store.set("global", "autosave", autosave, save=True)
    return store


def _factory(tmp_path: Path, autosave: bool = False, extra: dict | None = None):
    """Фабрика контролов поверх временного профиля и страницы-заглушки."""
    store = _store(tmp_path, autosave, extra)
    page = _StubPage()
    deps = SettingsDeps(
        picker=PathPicker(page),  # type: ignore[arg-type]
        opener=LinkOpener(page),  # type: ignore[arg-type]
    )
    return store, SettingsControls(page, store, deps)  # type: ignore[arg-type]


def _built(controls: SettingsControls, slug: str, key: str) -> SettingControl:
    """Контрол настройки схемы, у которого уже собрана строка."""
    category = controls.store.schema.require(slug)
    control = controls.build(category, category.spec(key))  # type: ignore[arg-type]
    control.control  # собирает редактор и запускает show_value()
    return control


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"type": "string", "label": "s", "default": ""}, TextSettingControl),
        ({"type": "text", "label": "t", "default": ""}, TextSettingControl),
        ({"type": "integer", "label": "i", "default": 1}, NumberSettingControl),
        ({"type": "number", "label": "n", "default": 1.0}, NumberSettingControl),
        ({"type": "boolean", "label": "b", "default": False}, BooleanSettingControl),
        ({"type": "date", "label": "d", "default": ""}, DateTimeSettingControl),
        ({"type": "time", "label": "t", "default": ""}, DateTimeSettingControl),
        ({"type": "datetime", "label": "dt", "default": ""}, DateTimeSettingControl),
        ({"type": "color", "label": "c", "default": "#000000"}, ColorSettingControl),
        (
            {
                "type": "choice",
                "label": "ch",
                "default": "a",
                "choices": [{"value": "a", "label": "A"}],
            },
            ChoiceSettingControl,
        ),
        (
            {
                "type": "multi_choice",
                "label": "mc",
                "default": [],
                "choices": [{"value": "a", "label": "A"}],
            },
            MultiChoiceSettingControl,
        ),
        ({"type": "file", "label": "f", "default": ""}, PathSettingControl),
        ({"type": "directory", "label": "dir", "default": ""}, PathSettingControl),
        ({"type": "image", "label": "img", "default": ""}, PathSettingControl),
        (
            {"type": "link", "link_type": "url", "label": "l", "default": ""},
            LinkSettingControl,
        ),
    ],
)
def test_every_value_type_gets_its_widget(
    tmp_path: Path, payload: dict, expected: type
) -> None:
    """Каждому типу значения схемы соответствует свой виджет."""
    _store_obj, controls = _factory(tmp_path)
    category = Category.from_dict(
        {"slug": "demo", "title": "Demo", "settings": {"value": payload}}
    )
    spec = category.spec("value")
    assert spec is not None
    assert isinstance(controls.build(category, spec), expected)


def test_boolean_widget_writes_store_and_file(tmp_path: Path) -> None:
    """Переключатель пишет значение в хранилище и в файл профиля."""
    store, controls = _factory(tmp_path, autosave=True)
    control = _built(controls, "global", "confirm_on_exit")

    assert control.commit(False) is True
    assert store.get("global", "confirm_on_exit") is False
    assert (tmp_path / ".termoclub" / SETTINGS_DIR / "global.json").exists()


def test_number_widget_rejects_out_of_range(tmp_path: Path) -> None:
    """Число вне границ схемы не пишется, вместо этого показывается ошибка."""
    store, controls = _factory(tmp_path)
    control = _built(controls, "terminal-pyte", "font_size")

    assert control.commit(999) is False
    assert store.get("terminal-pyte", "font_size") == 13
    assert control._error is not None and control._error.visible


def test_choice_widget_offers_and_writes_schema_choices(tmp_path: Path) -> None:
    """Выпадающий список показывает варианты схемы и пишет выбранный."""
    store, controls = _factory(tmp_path)
    control = _built(controls, "global", "theme_mode")

    dropdown = control.control_for_editor
    assert isinstance(dropdown, ft.Dropdown)
    assert {option.key for option in dropdown.options} == {"system", "light", "dark"}
    assert control.commit("light") is True
    assert store.get("global", "theme_mode") == "light"


def test_datetime_widget_roundtrip(tmp_path: Path) -> None:
    """Дата, время и дата-со-временем читаются и пишутся виджетом."""
    _store_obj, controls = _factory(
        tmp_path,
        extra={
            "slug": "demo",
            "title": "Demo",
            "settings": {
                "at": {"type": "datetime", "label": "at", "default": ""},
                "clock": {"type": "time", "label": "clock", "default": ""},
            },
        },
    )
    date_control = _built(controls, "global", "update_check_date")
    assert date_control.commit(date(2026, 3, 1)) is True
    date_control.show_value(controls.store.get("global", "update_check_date"))
    assert date_control._field.value == "2026-03-01"

    at = _built(controls, "demo", "at")
    assert at.commit(datetime(2026, 3, 1, 12, 30)) is True
    assert at._field.value == "2026-03-01 12:30"
    assert controls.store.get("demo", "at") == datetime(2026, 3, 1, 12, 30)

    clock = _built(controls, "demo", "clock")
    assert clock.commit(time(7, 5)) is True
    assert clock._field.value == "07:05"
    assert controls.store.get("demo", "clock") == time(7, 5)


def test_datetime_picker_writes_selected_value(tmp_path: Path) -> None:
    """Выбор в пикере даты превращается в значение настройки."""
    store, controls = _factory(tmp_path)
    control = _built(controls, "global", "update_check_date")

    control._open_date(None)  # type: ignore[arg-type]
    shown = control.page.shown_dialogs[-1]
    assert isinstance(shown, ft.DialogControl)  # тип, который принимает show_dialog
    assert isinstance(shown, ft.DatePicker)

    event = SimpleEvent(datetime(2026, 5, 17))
    control._on_date_change(event)  # type: ignore[arg-type]
    assert store.get("global", "update_check_date") == date(2026, 5, 17)
    assert control._field.value == "2026-05-17"


def test_color_widget_normalizes_and_persists(tmp_path: Path) -> None:
    """Цвет из поля приводится к виду `#rrggbb` и сохраняется."""
    store, controls = _factory(tmp_path, autosave=True)
    control = _built(controls, "appearance", "theme_seed")

    control._pick("#AABBCC")
    assert store.get("appearance", "theme_seed") == "#aabbcc"
    assert control._field.value == "#aabbcc"  # канонический вид из хранилища


def test_path_widget_writes_typed_path(tmp_path: Path) -> None:
    """Поле пути пишет путь без диалога (web-режим и ручной ввод)."""
    store, controls = _factory(tmp_path)
    control = _built(controls, "global", "workspace_directory")

    control._field.value = str(tmp_path)
    control._on_submit(None)  # type: ignore[arg-type]
    assert store.get("global", "workspace_directory") == str(tmp_path)


def test_link_widget_validates_url(tmp_path: Path) -> None:
    """Ссылка-адрес проверяется схемой: мусор не пишется."""
    store, controls = _factory(tmp_path)
    control = _built(controls, "global", "documentation_link")

    assert control.commit("not a url") is False
    assert control.commit("https://example.org/docs") is True
    assert store.get("global", "documentation_link") == "https://example.org/docs"


def test_multi_choice_widget_writes_a_list(tmp_path: Path) -> None:
    """Множественный выбор пишет список вариантов."""
    _store_obj, controls = _factory(
        tmp_path,
        extra={
            "slug": "demo",
            "title": "Demo",
            "settings": {
                "tags": {
                    "type": "multi_choice",
                    "label": "tags",
                    "default": [],
                    "choices": [
                        {"value": "a", "label": "A"},
                        {"value": "b", "label": "B"},
                        {"value": "c", "label": "C"},
                        {"value": "d", "label": "D"},
                        {"value": "e", "label": "E"},
                    ],
                }
            },
        },
    )
    control = _built(controls, "demo", "tags")
    assert isinstance(control, MultiChoiceSettingControl)
    for key, box in control._checks.items():
        box.value = key in {"b", "d"}
    control._on_check(None)  # type: ignore[arg-type]
    assert controls.store.get("demo", "tags") == ["b", "d"]


def test_value_from_store_is_shown_in_widget(tmp_path: Path) -> None:
    """Значение из хранилища попадает в виджет (обратное направление)."""
    store, controls = _factory(tmp_path)
    control = _built(controls, "terminal-pyte", "refresh_rate")
    assert control._field.value == "20"

    store.set("terminal-pyte", "refresh_rate", 45)
    control.show_value(store.get("terminal-pyte", "refresh_rate"))
    assert control._field.value == "45"


def test_unknown_value_type_falls_back_to_text_widget(tmp_path: Path) -> None:
    """Тип вне реестра виджетов не ломает категорию: даётся текстовое поле."""
    _store_obj, controls = _factory(tmp_path)
    category = Category.from_dict(
        {"slug": "demo", "title": "Demo", "settings": {"value": {"type": "string", "default": ""}}}
    )
    unknown = SimpleNamespace(
        key="value",
        type="brand-new-type",  # тип, которого ещё нет в реестре виджетов
        title="Value",
        description="",
        default="",
        pattern=None,
        multiline=False,
        readonly=False,
        requires_restart=False,
        unit="",
    )
    assert isinstance(controls.build(category, unknown), TextSettingControl)  # type: ignore[arg-type]


def test_panel_builds_rows_and_resets_category(tmp_path: Path) -> None:
    """Панель строит строки категории и умеет сбросить её целиком."""
    store = _store(tmp_path)
    view = SettingsPage(_StubPage(), store)  # type: ignore[arg-type]

    assert store.schema.find(DEFAULT_CATEGORY) is not None
    assert {row.spec.key for row in view.panel.rows} == {
        spec.key for spec in store.schema.require(DEFAULT_CATEGORY).settings
    }

    store.set("global", "log_level", "DEBUG")
    view.panel._on_reset_category(store.schema.require("global"))
    assert store.get("global", "log_level") == "INFO"


def test_page_selects_categories_from_the_sidebar(tmp_path: Path) -> None:
    """Выбор категории меняет содержимое правой панели."""
    store = _store(tmp_path)
    view = SettingsPage(_StubPage(), store)  # type: ignore[arg-type]

    view.select("terminal-smartcli")
    assert view.panel.slug == "terminal-smartcli"
    assert view.sidebar.active == "terminal-smartcli"
    assert {row.spec.key for row in view.panel.rows} == {
        spec.key for spec in store.schema.require("terminal-smartcli").settings
    }


def test_settings_session_is_a_workspace_tab(tmp_path: Path) -> None:
    """Вкладка Settings — обычная сессия workspace с двухколоночным экраном."""
    store = _store(tmp_path)
    session = SettingsSession(store=store, page=_StubPage())  # type: ignore[arg-type]

    assert session.kind == "settings"
    assert session.icon == "gear"
    content = session.get_content()
    assert isinstance(content, ft.Row)
    assert session.get_content() is content  # экран собирается один раз
    assert session.view is not None
    assert session.view.sidebar.active == DEFAULT_CATEGORY


def test_session_requires_page_to_build_ui(tmp_path: Path) -> None:
    """Без страницы вкладка не может собрать виджеты (явная ошибка)."""
    session = SettingsSession(store=_store(tmp_path))
    with pytest.raises(RuntimeError):
        session.get_content()


def test_readonly_store_rejects_widget_writes(tmp_path: Path) -> None:
    """Режим «только чтение» запрещает запись из виджета."""
    store, controls = _factory(tmp_path)
    control = _built(controls, "global", "theme_mode")
    store._readonly = True

    assert control.commit("light") is False
    assert control._error is not None and "read-only" in control._error.value


def test_sidebar_marks_changed_categories(tmp_path: Path) -> None:
    """Левая панель помечает категории с изменёнными настройками."""
    store = _store(tmp_path, autosave=True)  # autosave совпадает с умолчанием
    view = SettingsPage(_StubPage(), store)  # type: ignore[arg-type]
    assert view.sidebar._is_modified("global") is False

    store.set("global", "log_level", "DEBUG")
    assert view.sidebar._is_modified("global") is True
    assert view.sidebar._is_modified("appearance") is False


def test_multi_choice_segments_get_a_list(tmp_path: Path) -> None:
    """Сегменты получают список: `set` во Flet 1.0 не сериализуется в msgpack.

    Короткий список вариантов рисуется сегментами, и выбранное обязано быть
    списком: `set` конструктор принимает, но кодек Flet особо обрабатывает
    только `list`/`dict`/dataclass — отрисовка падала на
    «can not serialize 'set' object».
    """
    _store_obj, controls = _factory(
        tmp_path,
        extra={
            "slug": "demo",
            "title": "Demo",
            "settings": {
                "tags": {
                    "type": "multi_choice",
                    "label": "tags",
                    "default": [],
                    "choices": [{"value": "a", "label": "A"}],
                }
            },
        },
    )
    control = _built(controls, "demo", "tags")

    assert isinstance(control, MultiChoiceSettingControl)
    editor = control.control_for_editor
    assert isinstance(editor, ft.SegmentedButton)
    assert isinstance(editor.selected, list)

    control.show_value(["a"])
    assert editor.selected == ["a"]
    assert isinstance(editor.selected, list)


def test_multi_choice_without_choices_shows_a_hint(tmp_path: Path) -> None:
    """Пустой список вариантов — подсказка, а не сегменты без сегментов.

    Flet отвергает `SegmentedButton` без единого сегмента на исходящей
    валидации («segments must contain at least one visible Control»), а
    `ValueError` из `update()` уходил наверх и ломал вкладку настроек целиком.
    Именно в таком состоянии живёт `plugins.disabled_plugins`: варианты
    появляются только после сканирования плагинов.
    """
    _store_obj, controls = _factory(tmp_path)
    control = _built(controls, "plugins", "disabled_plugins")

    assert isinstance(control, MultiChoiceSettingControl)
    editor = control.control_for_editor
    assert isinstance(editor, ft.Text)
    assert editor.value == EMPTY_CHOICES_TEXT
    control.show_value(["demo"])  # не должно падать и ничего не рисует
    # Состояние контрола проходит валидацию клиента и сериализацию в msgpack.
    assert check_control(editor) == []


def test_multi_choice_segments_write_in_schema_order(tmp_path: Path) -> None:
    """Выбранные сегменты пишутся в порядке вариантов схемы."""
    _store_obj, controls = _factory(
        tmp_path,
        extra={
            "slug": "demo",
            "title": "Demo",
            "settings": {
                "tags": {
                    "type": "multi_choice",
                    "label": "tags",
                    "default": [],
                    "choices": [
                        {"value": "a", "label": "A"},
                        {"value": "b", "label": "B"},
                        {"value": "c", "label": "C"},
                    ],
                }
            },
        },
    )
    control = _built(controls, "demo", "tags")
    editor = control.control_for_editor
    assert isinstance(editor, ft.SegmentedButton)

    editor.selected = ["c", "a"]
    control._on_segments(None)  # type: ignore[arg-type]
    assert controls.store.get("demo", "tags") == ["a", "c"]


class SimpleEvent:
    """Событие Flet для тестов обработчиков без запуска приложения."""

    def __init__(self, value: object) -> None:
        self.control = type("Control", (), {"value": value})()


# --- Узкая строка настроек: текст не «разъезжается» по высоте ---


def test_setting_text_column_has_a_readable_minimum_width(tmp_path: Path) -> None:
    """Колонка с подписью и описанием не сжимается ниже читаемого минимума.

    В узком окне на неё оставалось всё меньше места, и `ft.Text` начинал
    переносить по одному символу: описание вырастало в вертикальную полосу.
    """
    _, controls = _factory(tmp_path)
    control = _built(controls, "global", "theme_mode")
    widths = [
        child.width
        for child in control.control.content.controls
        if isinstance(child, ft.Container) and child.width
    ]
    assert TEXT_MIN_WIDTH in widths, widths


def test_setting_description_is_capped_and_ellipsized(tmp_path: Path) -> None:
    """Длинное описание ограничено по строкам и обрезается многоточием."""
    _, controls = _factory(tmp_path)
    control = _built(controls, "global", "theme_mode")
    spec = control.category.spec("theme_mode")
    assert spec is not None and spec.description, "у настройки должно быть описание"

    descriptions = [
        child
        for child in control.control.content.controls[0].content.controls
        if isinstance(child, ft.Text) and child.value == spec.description
    ]
    assert descriptions, "описание должно быть в строке настроек"
    description = descriptions[0]
    assert description.max_lines == 2
    assert description.overflow == ft.TextOverflow.ELLIPSIS
    # Обрезанный текст целиком читается в подсказке.
    assert description.tooltip == spec.description