# termoclub/core/storage/backends/ProfileBackend.py
"""Бэкенд операций с файлами в профиле пользователя (`~/.termoclub`)."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.storage.StorageBackend import StorageBackend

logger = logging.getLogger(__name__)


class ProfileBackend(StorageBackend):
    """Файловые операции внутри профиля пользователя.

    Все относительные пути резолвятся строго внутри `root`;
    выход за пределы корня отклоняется с `ValueError`.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        super().__init__(root or Path.home() / ".termoclub")

    @classmethod
    def default(cls) -> "ProfileBackend":
        """Бэкенд профиля по умолчанию (`~/.termoclub`)."""
        return cls(Path.home() / ".termoclub")

    def _resolve(self, path: str | Path) -> Path:
        """Резолвит относительный путь строго внутри корня."""
        target = (self._root / Path(path)).resolve()
        root = self._root.resolve()
        if target != root and not target.is_relative_to(root):
            raise ValueError(f"Path escapes storage root: {path!r}")
        return target

    def create_file(self, path: str | Path, content: str = "") -> Path:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("ProfileBackend: created file %s", target)
        return target

    def create_dir(self, path: str | Path) -> Path:
        target = self._resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        logger.info("ProfileBackend: created dir %s", target)
        return target

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        return self._resolve(path).read_text(encoding=encoding)

    def read_bytes(self, path: str | Path) -> bytes:
        return self._resolve(path).read_bytes()

    def write_text(self, path: str | Path, content: str, encoding: str = "utf-8") -> Path:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        logger.info("ProfileBackend: wrote file %s", target)
        return target

    def write_bytes(self, path: str | Path, content: bytes) -> Path:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        logger.info("ProfileBackend: wrote file %s", target)
        return target

    def copy(self, src: str | Path, dst: str | Path) -> Path:
        src_path = self._resolve(src)
        dst_path = self._resolve(dst)
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
        logger.info("ProfileBackend: copied %s -> %s", src_path, dst_path)
        return dst_path

    def delete(self, path: str | Path) -> None:
        target = self._resolve(path)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
        logger.info("ProfileBackend: deleted %s", target)

    def exists(self, path: str | Path) -> bool:
        try:
            return self._resolve(path).exists()
        except ValueError:
            return False
