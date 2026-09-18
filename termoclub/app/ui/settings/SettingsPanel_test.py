# termoclub/app/ui/settings/SettingsPanel_test.py
"""Вкладка настроек целиком: контракт клиента Flet для каждой категории.

Окно Flet в тестах не поднимается, но проверяется именно то, что ломало
вкладку: клиент отвергает часть состояний контролов, а Python падает раньше —
на исходящей валидации (`BaseControl._before_update_safe`) или при
сериализации в msgpack. Оба шага прогоняются по всему дереву контролов
каждой категории схемы, включая пустые списки вариантов (как у
`plugins.disabled_plugins` до первого сканирования плагинов).
"""
from __future__ import annotations

from pathlib import Path

import flet as ft

from app.pages.settings import SettingsPage
from app.ui.flet_contract import check_tree
from core.settings.SettingsStore import SettingsStore
from core.storage.backends.ProfileBackend import ProfileBackend
from core.storage.FileManager import FileManager


class _StubPage:
    """Минимальная страница Flet: сервисы и диалоги (окно не нужно)."""

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


def _page_view(tmp_path: Path) -> SettingsPage:
    """Экран настроек поверх временного профиля."""
    fm = FileManager(ProfileBackend(tmp_path / ".termoclub"))
    store = SettingsStore(fm)
    store.set("global", "autosave", False, save=True)
    return SettingsPage(_StubPage(), store)  # type: ignore[arg-type]


def test_every_category_passes_the_client_contract(tmp_path: Path) -> None:
    """Каждая категория схемы валидируется и сериализуется без ошибок.

    Так ловится, например, `SegmentedButton` без сегментов: Flet отвечает
    `ValueError: segments must contain at least one visible Control`, и вкладка
    настроек падала на открытии категории.
    """
    view = _page_view(tmp_path)
    slugs = [category.slug for category in view.store.categories]
    assert slugs, "схема настроек должна содержать категории"

    failures: list[str] = []
    for slug in slugs:
        view.panel.show(slug)
        assert view.panel.slug == slug
        failures.extend(f"[{slug}] {problem}" for problem in check_tree(view.panel.control))
    assert not failures, "контракт клиента Flet нарушен:\n" + "\n".join(failures)


def test_whole_page_exposes_both_columns(tmp_path: Path) -> None:
    """Экран — левая колонка (заголовок над шевронами), разделитель и панель."""
    view = _page_view(tmp_path)
    root = view.control
    assert isinstance(root, ft.Row)
    kinds = [type(child).__name__ for child in root.controls]
    assert "VerticalDivider" in kinds
    # Правая панель показывает настройки выбранной категории.
    assert view.panel.rows, "у категории по умолчанию должны быть строки настроек"


def test_settings_header_sits_above_the_category_chevrons(tmp_path: Path) -> None:
    """Заголовок «Settings» стоит над списком шевронов, а не слева от него.

    Иначе заголовок занимал отдельную колонку по всей высоте вкладки, и под
    ним оставалась пустая полоса, а список категорий начинался ниже.
    """
    view = _page_view(tmp_path)
    left_column = view.control.controls[0].content
    assert isinstance(left_column, ft.Column)
    header, chevrons = left_column.controls
    assert isinstance(header, ft.Column)
    texts = [control.value for control in header.controls if isinstance(control, ft.Text)]
    assert texts[0] == "Settings"
    # Вторым идёт именно список категорий, а не заголовок: `sidebar.control`
    # — свойство, собирающее контейнер заново, поэтому сравниваем структуру
    # (колонка с шевронами внутри), а не тождество объектов.
    assert isinstance(chevrons, ft.Container)
    assert isinstance(chevrons.content, ft.Column)
    assert chevrons.content is view.sidebar._column
    # И это единственная колонка слева: заголовок больше не отдельный столбец.
    assert len(view.control.controls) == 3


def test_every_widget_of_the_page_is_serializable(tmp_path: Path) -> None:
    """Дерево экрана целиком (обе колонки) готово к отправке клиенту."""
    view = _page_view(tmp_path)
    assert check_tree(view.control) == []
