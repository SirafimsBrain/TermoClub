# termoclub/app/ui/settings/PathPicker.py
"""Диалоги выбора пути для настроек типов `file`/`directory`/`image`/`link`.

Flet отдаёт файловые диалоги сервисом (`ft.FilePicker`), который нужно
зарегистрировать на странице, а вызовы у него асинхронные. GUI-слой
настроек не должен знать ни того, ни другого, поэтому весь сервис спрятан
здесь: контролы получают простые «выбрать файл» / «выбрать каталог».

В web-режиме (и там, где сервис недоступен) диалог не открывается:
возвращается None, а поле остаётся редактируемым вручную.
"""
from __future__ import annotations

import logging

import flet as ft

logger = logging.getLogger(__name__)


class PathPicker:
    """Обёртка `ft.FilePicker`: выбор файла, изображения и каталога."""

    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self._picker: ft.FilePicker | None = None
        self._broken = False

    @property
    def available(self) -> bool:
        """True, если диалоги выбора пути работают на этой платформе."""
        return not self._broken

    async def pick_file(
        self,
        extensions: list[str] | None = None,
        title: str = "Choose a file",
    ) -> str | None:
        """Возвращает путь выбранного файла (None — отмена или сбой)."""
        picker = self._ensure_picker()
        if picker is None:
            return None
        try:
            files = await picker.pick_files(
                dialog_title=title,
                file_type=ft.FilePickerFileType.CUSTOM if extensions else ft.FilePickerFileType.ANY,
                allowed_extensions=[e.lstrip(".") for e in extensions or []],
                allow_multiple=False,
            )
        except Exception as exc:  # noqa: BLE001 — платформа может не поддерживать
            self._mark_broken(exc)
            return None
        if not files:
            return None
        return files[0].path

    async def pick_directory(self, title: str = "Choose a directory") -> str | None:
        """Возвращает путь выбранного каталога (None — отмена или сбой)."""
        picker = self._ensure_picker()
        if picker is None:
            return None
        try:
            return await picker.get_directory_path(dialog_title=title)
        except Exception as exc:  # noqa: BLE001 — web-режим и урезанные сборки
            self._mark_broken(exc)
            return None

    def _ensure_picker(self) -> ft.FilePicker | None:
        """Создаёт сервис один раз и регистрирует его на странице."""
        if self._broken:
            return None
        if self._picker is not None:
            return self._picker
        try:
            self._picker = ft.FilePicker()
            self._page.services.append(self._picker)
        except Exception as exc:  # noqa: BLE001 — сервис недоступен в этом режиме
            self._mark_broken(exc)
            return None
        return self._picker

    def _mark_broken(self, exc: BaseException) -> None:
        """Помечает диалоги недоступными, чтобы не пытаться снова."""
        self._broken = True
        logger.warning("PathPicker: file dialogs unavailable: %s", exc)