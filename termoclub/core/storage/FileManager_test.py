# termoclub/core/storage/FileManager_test.py
"""Тесты обёртки файловых операций и бэкенда профиля."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.storage.backends.ProfileBackend import ProfileBackend
from core.storage.FileManager import FileManager


def _manager(tmp_path: Path) -> FileManager:
    return FileManager(ProfileBackend(tmp_path / ".termoclub"))


def test_create_and_read_text(tmp_path: Path) -> None:
    """Создание файла и чтение содержимого."""
    fm = _manager(tmp_path)
    fm.create_file("notes/hello.txt", "hi")
    assert fm.read_text("notes/hello.txt") == "hi"


def test_write_modifies_existing_file(tmp_path: Path) -> None:
    """Изменение перезаписывает файл."""
    fm = _manager(tmp_path)
    fm.write_text("a.txt", "one")
    fm.write_text("a.txt", "two")
    assert fm.read_text("a.txt") == "two"


def test_write_and_read_bytes(tmp_path: Path) -> None:
    """Байтовые чтение/запись."""
    fm = _manager(tmp_path)
    fm.write_bytes("b.bin", b"\x00\x01")
    assert fm.read_bytes("b.bin") == b"\x00\x01"


def test_copy_file_and_dir(tmp_path: Path) -> None:
    """Копирование файла и директории."""
    fm = _manager(tmp_path)
    fm.write_text("src/f.txt", "data")
    fm.copy("src/f.txt", "dst/f.txt")
    assert fm.read_text("dst/f.txt") == "data"
    fm.copy("src", "src_copy")
    assert fm.read_text("src_copy/f.txt") == "data"


def test_delete_file_and_dir_recursively(tmp_path: Path) -> None:
    """Удаление файла и директории с содержимым."""
    fm = _manager(tmp_path)
    fm.write_text("d/f.txt", "x")
    fm.delete("d/f.txt")
    assert not fm.exists("d/f.txt")
    fm.delete("d")
    assert not fm.exists("d")


def test_exists_and_create_dir(tmp_path: Path) -> None:
    """exists() и создание директорий."""
    fm = _manager(tmp_path)
    assert not fm.exists("new")
    fm.create_dir("new/nested")
    assert fm.exists("new/nested")


def test_path_escape_is_rejected(tmp_path: Path) -> None:
    """Выход за пределы корня хранилища запрещён."""
    fm = _manager(tmp_path)
    with pytest.raises(ValueError):
        fm.write_text("../escape.txt", "nope")
    assert not fm.exists("../escape.txt")


def test_archive_and_remote_ops_are_stubs(tmp_path: Path) -> None:
    """Архивы и удалённые операции — заглушки."""
    fm = _manager(tmp_path)
    fm.write_text("f.txt", "x")
    with pytest.raises(NotImplementedError):
        fm.archive("f.txt", "f.zip")
    with pytest.raises(NotImplementedError):
        fm.extract("f.zip", "out")
    with pytest.raises(NotImplementedError):
        fm.download("https://example.com/f", "f.txt")
    with pytest.raises(NotImplementedError):
        fm.upload("f.txt", "https://example.com/f")


def test_default_backend_points_to_user_profile() -> None:
    """Бэкенд по умолчанию — профиль пользователя."""
    backend = ProfileBackend.default()
    assert backend.root == Path.home() / ".termoclub"
