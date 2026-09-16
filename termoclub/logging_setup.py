# termoclub/logging_setup.py
"""Централизованная настройка логирования TermoClub.

Пишет в файл (logs/termoclub.log) и в консоль.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOGS_DIR / "termoclub.log"

#: Метка на хендлерах самого приложения: по ней setup_logging узнаёт свои.
_HANDLER_MARK = "termoclub"


def setup_logging(level: int = logging.INFO) -> None:
    """Настраивает корневой логгер: файл + консоль.

    Идемпотентна: `flet run` перезагружает модуль приложения в том же
    процессе, а повторный вызов со `addHandler` без проверки удваивал бы
    хендлеры и писал каждую запись дважды, трижды и так далее.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        if getattr(handler, "_termoclub", False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    for handler in (file_handler, console_handler):
        setattr(handler, "_termoclub", _HANDLER_MARK)
        root.addHandler(handler)