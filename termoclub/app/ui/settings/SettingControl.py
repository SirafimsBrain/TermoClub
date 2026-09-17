# termoclub/app/ui/settings/SettingControl.py
"""База для виджетов настроек: подпись, редактор значения, сброс.

GUI-слой не работает с файлами: значение читается и пишется только через
`SettingsStore`. Наследник отвечает за две вещи — собрать редактор под свой
тип (`build_editor`) и показать текущее значение (`show_value`); всё
остальное (строка с подписью, описание, ошибка валидации, кнопка сброса,
бейдж «нужен перезапуск», запись в хранилище) делает этот класс.

Ошибка валидации не выбрасывается наружу: она показывается под полем, а
значение в хранилище остаётся прежним. Так пользователь видит, что именно
не так, и не теряет остальные правки.
"""
from __future__ import annotations

from collections.abc import Callable

import flet as ft

from app.ui.FontAwesome import FontAwesome
from core.settings.Category import Category
from core.settings.SettingSpec import SettingSpec
from core.settings.SettingsStore import SettingsStore
from core.settings.SettingsValidationError import SettingsValidationError

#: Цвет подписи-описания и текста ошибки.
MUTED = ft.Colors.ON_SURFACE_VARIANT


class SettingControl:
    """Строка настроек: подпись, редактор и служебные действия."""

    #: Ширина колонки редактора (пиксели).
    EDITOR_WIDTH = 320

    def __init__(
        self,
        page: ft.Page,
        store: SettingsStore,
        category: Category,
        spec: SettingSpec,
        on_changed: Callable[[str, str], None] | None = None,
    ) -> None:
        self.page = page
        self.store = store
        self.category = category
        self.spec = spec
        self.on_changed = on_changed
        self._error: ft.Text | None = None
        self._editor: ft.Control | None = None
        self._row: ft.Container | None = None
        self._reset_button: ft.IconButton | None = None

    # --- Сборка ---

    @property
    def control(self) -> ft.Control:
        """Строка настроек (строится один раз)."""
        if self._row is None:
            self._editor = self.build_editor()
            self._error = ft.Text("", size=11, color=ft.Colors.ERROR, visible=False)
            self._row = ft.Container(
                padding=ft.Padding.symmetric(vertical=6, horizontal=4),
                content=ft.Row(
                    [
                        ft.Column(
                            [self._label(), self._description()],
                            spacing=2,
                            expand=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        ft.Container(content=self._editor, width=self.EDITOR_WIDTH),
                        self._reset(),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
            )
            self.show_value(self.value)
        return self._row

    def build_editor(self) -> ft.Control:
        """Строит редактор значения (переопределяется наследником)."""
        raise NotImplementedError

    def show_value(self, value: object) -> None:
        """Показывает значение в редакторе (переопределяется наследником)."""
        raise NotImplementedError

    @property
    def control_for_editor(self) -> ft.Control | None:
        """Редактор значения (доступен после сборки строки)."""
        return self._editor

    # --- Значение ---

    @property
    def value(self) -> object:
        """Текущее значение настройки из хранилища."""
        return self.store.get(self.category.slug, self.spec.key)

    def commit(self, value: object) -> bool:
        """Пишет значение через хранилище; ошибку показывает под полем."""
        if self.spec.readonly or self.category.readonly or self.store.readonly:
            self.show_error("Setting is read-only.")
            return False
        try:
            stored = self.store.set(
                self.category.slug, self.spec.key, value, save=self.autosave
            )
        except SettingsValidationError as exc:
            self.show_error(exc.message)
            return False
        except Exception as exc:  # noqa: BLE001 — пользователю нужен текст, а не трейс
            self.show_error(str(exc))
            return False
        self.show_error("")
        self.show_value(stored)  # значение могло быть нормализовано схемой
        self.refresh_reset()
        if self.on_changed is not None:
            self.on_changed(self.category.slug, self.spec.key)
        return True

    @property
    def autosave(self) -> bool:
        """Писать ли файл сразу (настройка `global.autosave`)."""
        try:
            return bool(self.store.get("global", "autosave"))
        except Exception:  # noqa: BLE001 — категории global может не быть в схеме
            return True

    def reset(self, _event: ft.ControlEvent | None = None) -> None:
        """Возвращает настройку к умолчанию и обновляет виджет."""
        try:
            value = self.store.reset(self.category.slug, self.spec.key, save=self.autosave)
        except Exception as exc:  # noqa: BLE001 — сброс не должен ронять вкладку
            self.show_error(str(exc))
            return
        self.show_error("")
        self.show_value(value)
        self.refresh_reset()
        if self.on_changed is not None:
            self.on_changed(self.category.slug, self.spec.key)

    def show_error(self, message: str) -> None:
        """Показывает/прячет текст ошибки валидации."""
        if self._error is None:
            return
        self._error.value = message
        self._error.visible = bool(message)
        self._safe_update(self._error)

    def refresh_reset(self) -> None:
        """Показывает кнопку сброса, только если значение отличается от умолчания."""
        if self._reset_button is None:
            return
        self._reset_button.visible = self.store.is_modified(
            self.category.slug, self.spec.key
        )
        self._safe_update(self._reset_button)

    # --- Части строки ---

    def _label(self) -> ft.Control:
        """Подпись настройки с пометками «нужен перезапуск» и «только чтение»."""
        parts: list[ft.Control] = [ft.Text(self.spec.title, size=13)]
        if self.spec.requires_restart:
            parts.append(
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=1, horizontal=6),
                    border_radius=4,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    content=ft.Text("restart", size=9, color=MUTED),
                )
            )
        if self.spec.readonly or self.category.readonly or self.store.readonly:
            parts.append(FontAwesome.icon("xmark", size=11, color=MUTED))
        return ft.Row(parts, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _description(self) -> ft.Control:
        """Описание настройки под подписью."""
        return ft.Text(self.spec.description or "", size=11, color=MUTED, visible=bool(self.spec.description))

    def _reset(self) -> ft.Control:
        """Кнопка сброса к умолчанию (видна только при изменённом значении)."""
        self._reset_button = ft.IconButton(
            icon=ft.Icons.RESTART_ALT,
            icon_size=16,
            tooltip="Reset to default",
            on_click=self.reset,
            visible=self.store.is_modified(self.category.slug, self.spec.key),
        )
        return self._reset_button

    @staticmethod
    def _safe_update(control: ft.Control | None) -> None:
        """Обновляет контрол, если он уже примонтирован к странице."""
        if control is None:
            return
        try:
            control.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.

    def _commit_text(self, value: str) -> None:
        """Пишет текстовое значение, если оно изменилось."""
        if value != self.value:
            self.commit(value)