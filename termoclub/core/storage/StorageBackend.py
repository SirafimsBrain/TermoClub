# termoclub/core/storage/StorageBackend.py
"""Абстрактный бэкенд файловых операций хранилища."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    """Интерфейс бэкенда: локальные операции + заглушки под будущее.

    Все пути — относительные, отсчитываются от корня бэкенда (`root`).
    Операции с архивами, удалённые операции и операции в других
    расположениях пока не реализованы: методы-заглушки бросают
    `NotImplementedError`.
    """

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).expanduser()

    @property
    def root(self) -> Path:
        """Корень бэкенда (все операции confined внутри него)."""
        return self._root

    def ensure_root(self) -> Path:
        """Создаёт корень бэкенда, если его нет."""
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root

    # --- Создание ---

    @abstractmethod
    def create_file(self, path: str | Path, content: str = "") -> Path:
        """Создаёт файл с содержимым (родители создаются автоматически)."""

    @abstractmethod
    def create_dir(self, path: str | Path) -> Path:
        """Создаёт директорию (включая промежуточные)."""

    # --- Чтение / изменение ---

    @abstractmethod
    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """Читает текстовый файл."""

    @abstractmethod
    def read_bytes(self, path: str | Path) -> bytes:
        """Читает файл как байты."""

    @abstractmethod
    def write_text(self, path: str | Path, content: str, encoding: str = "utf-8") -> Path:
        """Создаёт или перезаписывает текстовый файл."""

    @abstractmethod
    def write_bytes(self, path: str | Path, content: bytes) -> Path:
        """Создаёт или перезаписывает файл байтами."""

    # --- Копирование / удаление ---

    @abstractmethod
    def copy(self, src: str | Path, dst: str | Path) -> Path:
        """Копирует файл или директорию."""

    @abstractmethod
    def delete(self, path: str | Path) -> None:
        """Удаляет файл или директорию (рекурсивно)."""

    @abstractmethod
    def exists(self, path: str | Path) -> bool:
        """Проверяет существование пути."""

    # --- Архивы (заглушки) ---

    def archive(self, src: str | Path, dst: str | Path) -> Path:
        """Упаковывает путь в архив (пока не реализовано)."""
        raise NotImplementedError("archive() is not implemented yet")

    def extract(self, archive: str | Path, dst: str | Path) -> Path:
        """Распаковывает архив (пока не реализовано)."""
        raise NotImplementedError("extract() is not implemented yet")

    # --- Удалённые операции и другие расположения (заглушки) ---

    def download(self, url: str, dst: str | Path) -> Path:
        """Скачивает удалённый файл (пока не реализовано)."""
        raise NotImplementedError("download() is not implemented yet")

    def upload(self, src: str | Path, url: str) -> None:
        """Загружает файл в удалённое расположение (пока не реализовано)."""
        raise NotImplementedError("upload() is not implemented yet")
