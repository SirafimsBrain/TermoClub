# termoclub/app/ui/settings/LinkSettingControl.py
"""Виджет настроек-ссылок: `link` с типом ссылки из схемы.

Смысл ссылки задаёт схема (`LinkType`): внешний адрес и путь к файлу
открываются системой, служебная почтовая ссылка — почтовым клиентом,
путь к файлу или каталогу выбирается системным диалогом, внутренний
маршрут (route) проверяется приложением. Поле всегда редактируемо: тип
ссылки влияет только на набор кнопок рядом с ним.
"""
from __future__ import annotations

import flet as ft

from app.ui.settings.LinkOpener import LinkOpener
from app.ui.settings.PathPicker import PathPicker
from app.ui.settings.SettingControl import SettingControl
from core.settings.LinkType import LinkType


class LinkSettingControl(SettingControl):
    """Ссылка: адрес, почта, путь или внутренний маршрут."""

    def __init__(
        self,
        *args,
        picker: PathPicker,
        opener: LinkOpener,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._picker = picker
        self._opener = opener

    def build_editor(self) -> ft.Control:
        """Поле ссылки и действия, допустимые её типом."""
        self._field = ft.TextField(
            value=str(self.value or ""),
            text_size=13,
            dense=True,
            expand=True,
            hint_text=self._hint(),
            read_only=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_submit=self._on_submit,
            on_blur=self._on_submit,
        )
        return ft.Row(
            [ft.Container(content=self._field, expand=True), *self._actions()],
            spacing=4,
            tight=True,
        )

    def show_value(self, value: object) -> None:
        """Переносит ссылку из хранилища в поле."""
        if getattr(self, "_field", None) is None:
            return
        self._field.value = value if isinstance(value, str) else ""
        self._safe_update(self._field)

    @property
    def _link_type(self) -> LinkType:
        """Тип ссылки из схемы (по умолчанию — внешний адрес)."""
        return self.spec.link_type or LinkType.URL

    @property
    def _editable(self) -> bool:
        """False, если настройка только для чтения (кнопки отключаются)."""
        return not (self.spec.readonly or self.category.readonly or self.store.readonly)

    def _hint(self) -> str:
        """Подсказка формата ссылки."""
        return {
            LinkType.URL: "https://...",
            LinkType.EMAIL: "name@example.com",
            LinkType.FILE: "/path/to/file",
            LinkType.DIRECTORY: "/path/to/directory",
            LinkType.ROUTE: "/route",
        }[self._link_type]

    def _actions(self) -> list[ft.Control]:
        """Кнопки: выбор пути, открытие и копирование."""
        actions: list[ft.Control] = []
        if self._link_type is LinkType.DIRECTORY:
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.FOLDER_OPEN,
                    icon_size=18,
                    tooltip="Choose a directory",
                    disabled=not self._editable,
                    on_click=lambda _e: self.page.run_task(self._pick_directory),
                )
            )
        elif self._link_type is LinkType.FILE:
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.INSERT_DRIVE_FILE,
                    icon_size=18,
                    tooltip="Choose a file",
                    disabled=not self._editable,
                    on_click=lambda _e: self.page.run_task(self._pick_file),
                )
            )
        if self._link_type in (LinkType.URL, LinkType.EMAIL, LinkType.FILE):
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.OPEN_IN_NEW,
                    icon_size=18,
                    tooltip="Open",
                    on_click=lambda _e: self.page.run_task(self._open),
                )
            )
        actions.append(
            ft.IconButton(
                icon=ft.Icons.CONTENT_COPY,
                icon_size=18,
                tooltip="Copy",
                on_click=lambda _e: self.page.run_task(self._copy),
            )
        )
        return actions

    # --- Диалоги и сервисы ---

    async def _pick_file(self) -> None:
        """Выбирает файл для ссылки типа `file`."""
        chosen = await self._picker.pick_file(self.spec.extensions, "Choose a file")
        if chosen:
            self._field.value = chosen
            self.commit(chosen)

    async def _pick_directory(self) -> None:
        """Выбирает каталог для ссылки типа `directory`."""
        chosen = await self._picker.pick_directory("Choose a directory")
        if chosen:
            self._field.value = chosen
            self.commit(chosen)

    async def _open(self) -> None:
        """Открывает ссылку средствами системы."""
        url = (self._field.value or "").strip()
        if not url:
            return
        if self._link_type is LinkType.EMAIL and not url.startswith("mailto:"):
            url = f"mailto:{url}"
        self.show_error(await self._opener.open(url))

    async def _copy(self) -> None:
        """Копирует ссылку в буфер обмена."""
        self.show_error(await self._opener.copy((self._field.value or "").strip()))

    def _on_submit(self, _event: ft.ControlEvent) -> None:
        """Пишет ссылку, введённую вручную."""
        self.commit((self._field.value or "").strip())