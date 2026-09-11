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


def setup_logging(level: int = logging.INFO) -> None:
    """Настраивает корневой логгер: файл + консоль."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)