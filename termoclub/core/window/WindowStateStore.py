# termoclub/core/window/WindowStateStore.py
"""Посредник между файлом состояния окна и GUI.

Единственная точка работы с сохранённым состоянием главного окна: читает
снимок из профиля (`FileManager`), отдаёт его приложению, принимает
изменения и пишет их обратно. GUI не трогает файлы напрямую — как и с
настройками, доступ идёт через посредника.

Расположение файла — профиль пользователя (`~/.termoclub`), а не папка
настроек: это состояние конкретной машины, а не переносимая настройка.
Если профиль недоступен (нет прав, не смонтирован), класс переходит в
режим только для чтения: приложение получает умолчания, а запись молча
пропускается с записью в лог — состояние окна не то, ради чего стоит
показывать ошибку при запуске.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core.storage.FileManager import FileManager
from core.window.WindowState import WindowState

logger = logging.getLogger(__name__)

#: Файл состояния окна внутри профиля.
STATE_FILE = "window/state.json"


class WindowStateStore:
    """Чтение, изменение и сохранение состояния главного окна."""

    def __init__(
        self,
        file_manager: FileManager | None = None,
        path: str = STATE_FILE,
    ) -> None:
        self._path = path
        self._fm = file_manager if file_manager is not None else self._open_file_manager()
        self._readonly = self._fm is None
        self._state = self._load()

    # --- Доступ к состоянию ---

    @property
    def state(self) -> WindowState:
        """Текущее состояние окна."""
        return self._state

    @property
    def readonly(self) -> bool:
        """`True`, если профиль недоступен и запись невозможна."""
        return self._readonly

    def update(self, *, save: bool = True, **fields: object) -> WindowState:
        """Меняет поля состояния и (по умолчанию) сразу пишет файл.

        Пишем сразу, потому что отдельного момента «сохранить состояние»
        у окна нет: пользователь закрывает приложение когда угодно, и
        потерять последнее изменение размера или панели нельзя.
        """
        for name, value in fields.items():
            if not hasattr(self._state, name):
                raise AttributeError(f"Unknown window state field: {name!r}")
            setattr(self._state, name, value)
        if save:
            self.save()
        return self._state

    # --- Файл ---

    def load(self) -> WindowState:
        """Перечитывает состояние из файла профиля."""
        self._state = self._load()
        return self._state

    def save(self) -> bool:
        """Записывает состояние в профиль; `False`, если запись невозможна."""
        if self._readonly or self._fm is None:
            logger.debug("WindowStateStore: profile is read-only, state not saved")
            return False
        try:
            self._fm.write_text(
                self._path, json.dumps(self._state.to_dict(), indent=2)
            )
        except (OSError, ValueError) as exc:
            # Состояние окна не критично: не сохранить его — не повод падать.
            logger.error("WindowStateStore: failed to save state: %s", exc)
            return False
        return True

    def reset(self, *, save: bool = True) -> WindowState:
        """Возвращает умолчания (например, из пункта меню «сбросить вид»)."""
        self._state = WindowState()
        if save:
            self.save()
        return self._state

    # --- Внутреннее ---

    def _open_file_manager(self) -> FileManager | None:
        """Открывает `FileManager` профиля; недоступность — режим read-only."""
        try:
            return FileManager()
        except (OSError, ValueError, NotImplementedError) as exc:
            logger.error("WindowStateStore: profile is unavailable: %s", exc)
            return None

    def _load(self) -> WindowState:
        """Читает состояние из файла, при любой проблеме — умолчания.

        Отдельно различаем «файла ещё нет» (обычный первый запуск, пишем
        debug) и «файл есть, но испорчен» (предупреждение: пользователь
        потерял сохранённый вид, и об этом стоит знать из лога).
        """
        if self._fm is None:
            return WindowState()
        if not self._fm.exists(self._path):
            logger.debug("WindowStateStore: no saved state at %s", self._path)
            return WindowState()
        try:
            raw = self._fm.read_text(self._path)
            payload = json.loads(raw)
        except (OSError, ValueError) as exc:
            logger.warning(
                "WindowStateStore: cannot read %s (%s), using defaults",
                self._path,
                exc,
            )
            return WindowState()
        state = WindowState.from_dict(payload)
        logger.info(
            "WindowStateStore: restored %sx%s (left=%s, right=%s)",
            state.width,
            state.height,
            state.left_panel_open,
            state.right_panel_open,
        )
        return state