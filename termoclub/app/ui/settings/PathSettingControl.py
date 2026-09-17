# termoclub/app/ui/settings/PathSettingControl.py
"""Виджеты путей: `file`, `directory`, `image`.

Значение — путь строкой. Рядом с полем — кнопка выбора через системный
диалог (`PathPicker`); поле остаётся редактируемым вручную, потому что
диалогов может не быть (web-режим) и потому что путь удобно вставлять
из буфера. Для `image` дополнительно показывается предпросмотр файла.
"""
from __future__ import annotations

import flet as ft

from app.ui.settings.PathPicker import PathPicker
from app.ui.settings.SettingControl import MUTED, SettingControl

#: Заголовки диалогов по типу настройки.
DIALOG_TITLES = {
    "file": "Choose a file",
    "directory": "Choose a directory",
    "image": "Choose an image",
}


class PathSettingControl(SettingControl):
    """Путь к файлу, каталогу или изображению."""

    def __init__(self, *args, picker: PathPicker, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._picker = picker

    def build_editor(self) -> ft.Control:
        """Поле пути, кнопка выбора и (для изображений) предпросмотр."""
        value = str(self.value or "")
        self._field = ft.TextField(
            value=value,
            text_size=13,
            dense=True,
            expand=True,
            hint_text=self.spec.pattern or "",
            read_only=self.spec.readonly or self.category.readonly or self.store.readonly,
            on_submit=self._on_submit,
            on_blur=self._on_submit,
        )
        self._browse = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN if not self._is_image else ft.Icons.IMAGE,
            icon_size=18,
            tooltip=DIALOG_TITLES.get(self.spec.type.value, "Choose"),
            on_click=self._on_browse,
            disabled=self.spec.readonly or self.category.readonly or self.store.readonly,
        )
        self._field_host = ft.Container(
            content=self._field,
            expand=True,
            tooltip=None if self._picker.available else "File dialogs are unavailable; type the path",
        )
        row = ft.Row([self._field_host, self._browse], spacing=4, tight=True)
        if not self._is_image:
            return row
        self._preview = ft.Image(
            src=value or None,
            width=64,
            height=40,
            fit=ft.BoxFit.CONTAIN,
            border_radius=4,
            visible=bool(value),
        )
        self._preview_note = ft.Text("", size=10, color=MUTED, max_lines=1)
        return ft.Column(
            [row, ft.Row([self._preview, self._preview_note], spacing=8, tight=True)],
            spacing=4,
            tight=True,
        )

    def show_value(self, value: object) -> None:
        """Переносит путь хранилища в поле и предпросмотр."""
        text = value if isinstance(value, str) else ""
        self._field.value = text
        self._safe_update(self._field)
        if self._is_image:
            self._preview.src = text or None
            self._preview.visible = bool(text)
            self._safe_update(self._preview)

    @property
    def _is_image(self) -> bool:
        """True для настройки-изображения (у неё есть предпросмотр)."""
        return self.spec.type.value == "image"

    def _on_browse(self, _event: ft.ControlEvent) -> None:
        """Открывает системный диалог выбора пути (асинхронно)."""
        self.page.run_task(self._pick)

    async def _pick(self) -> None:
        """Выбирает путь и пишет его в настройку."""
        title = DIALOG_TITLES.get(self.spec.type.value, "Choose")
        if self.spec.type.value == "directory":
            chosen = await self._picker.pick_directory(title)
        else:
            chosen = await self._picker.pick_file(self.spec.extensions, title)
        if not chosen:
            self.show_error("")
            return
        self._field.value = chosen
        self.commit(chosen)

    def _on_submit(self, _event: ft.ControlEvent) -> None:
        """Пишет путь, введённый вручную."""
        self.commit((self._field.value or "").strip())