# termoclub/logging_setup_test.py
"""Тесты настройки логирования: повторный вызов не дублирует хендлеры."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

import logging_setup


@pytest.fixture()
def _isolated_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Уводит лог в tmp: тест не должен писать в рабочий каталог проекта."""
    monkeypatch.setattr(logging_setup, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(logging_setup, "LOG_FILE", tmp_path / "termoclub.log")
    root = logging.getLogger()
    before = list(root.handlers)
    yield root
    for handler in list(root.handlers):
        if getattr(handler, "_termoclub", False):
            root.removeHandler(handler)
            handler.close()
    for handler in before:
        if handler not in root.handlers:
            root.addHandler(handler)


def test_own_handlers_are_not_duplicated(_isolated_log: logging.Logger) -> None:
    """`flet run` перезагружает модуль: повторный вызов не удваивает вывод.

    Раньше хендлеры добавлялись без проверки, и каждая запись после
    перезагрузки писалась в файл и консоль дважды, трижды и так далее.
    """
    logging_setup.setup_logging()
    first = [h for h in _isolated_log.handlers if getattr(h, "_termoclub", False)]
    assert len(first) == 2  # файл + консоль
    logging_setup.setup_logging()
    second = [h for h in _isolated_log.handlers if getattr(h, "_termoclub", False)]
    assert len(second) == 2
    assert all(handler not in second for handler in first)


def test_foreign_handlers_are_kept(_isolated_log: logging.Logger) -> None:
    """Чужие хендлеры (например, pytest) не снимаются."""
    foreign = logging.NullHandler()
    _isolated_log.addHandler(foreign)
    logging_setup.setup_logging()
    assert foreign in _isolated_log.handlers


def test_level_is_applied(_isolated_log: logging.Logger) -> None:
    """Уровень корневого логгера выставляется по аргументу."""
    logging_setup.setup_logging(logging.DEBUG)
    assert _isolated_log.level == logging.DEBUG
    assert (logging_setup.LOGS_DIR / "termoclub.log").exists()
