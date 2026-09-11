# termoclub/core/storage/FileManager.py
"""Обёртка файловых операций: прячет хранилище от остальных классов.

Единственная точка доступа к данным пользователя. По умолчанию работает
с профилем (`~/.termoclub` через `ProfileBackend`); другие бэкенды
(удалённые операции, другие расположения) — заглушки, бросают
`NotImplementedError` из базового `StorageBackend`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.storage.backends.ProfileBackend import ProfileBackend
from core.storage.StorageBackend import StorageBackend

logger = logging.getLogger(__name__)


class FileManager:
    """Единый интерфейс стандартных файловых операций проекта."""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend = backend or ProfileBackend.default()
        self._backend.ensure_root()
        logger.info("FileManager: using storage root %s", self._backend.root)

    @property
    def backend(self) -> StorageBackend:
        """Активный бэкенд хранилища."""
        return self._backend

    @property
    def root(self) -> Path:
        """Корень хранилища."""
        return self._backend.root

    # --- Создание ---

    def create_file(self, path: str | Path, content: str = "") -> Path:
        """Создаёт файл с содержимым."""
        return self._backend.create_file(path, content)

    def create_dir(self, path: str | Path) -> Path:
        """Создаёт директорию."""
        return self._backend.create_dir(path)

    # --- Чтение / изменение ---

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """Читает текстовый файл."""
        return self._backend.read_text(path, encoding)

    def read_bytes(self, path: str | Path) -> bytes:
        """Читает файл как байты."""
        return self._backend.read_bytes(path)

    def write_text(self, path: str | Path, content: str, encoding: str = "utf-8") -> Path:
        """Создаёт или изменяет текстовый файл."""
        return self._backend.write_text(path, content, encoding)

    def write_bytes(self, path: str | Path, content: bytes) -> Path:
        """Создаёт или изменяет файл байтами."""
        return self._backend.write_bytes(path, content)

    # --- Копирование / удаление ---

    def copy(self, src: str | Path, dst: str | Path) -> Path:
        """Копирует файл или директорию."""
        return self._backend.copy(src, dst)

    def delete(self, path: str | Path) -> None:
        """Удаляет файл или директорию (рекурсивно)."""
        self._backend.delete(path)

    def exists(self, path: str | Path) -> bool:
        """Проверяет существование пути."""
        return self._backend.exists(path)

    # --- Архивы (заглушки, реализация позже) ---

    def archive(self, src: str | Path, dst: str | Path) -> Path:
        """Упаковывает путь в архив (пока не реализовано)."""
        return self._backend.archive(src, dst)

    def extract(self, archive: str | Path, dst: str | Path) -> Path:
        """Распаковывает архив (пока не реализовано)."""
        return self._backend.extract(archive, dst)

    # --- Удалённые операции (заглушки, реализация позже) ---

    def download(self, url: str, dst: str | Path) -> Path:
        """Скачивает удалённый файл (пока не реализовано)."""
        return self._backend.download(url, dst)

    def upload(self, src: str | Path, url: str) -> None:
        """Загружает файл в удалённое расположение (пока не реализовано)."""
        self._backend.upload(src, url)
