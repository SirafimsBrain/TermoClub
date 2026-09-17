# termoclub/core/settings/PluginInfo.py
"""Описание найденного плагина (манифест + наличие схемы настроек).

Сканер отдаёт такие записи наружу: их видят GUI (список отключаемых
плагинов) и хранилище (какие категории подхватывать). Сам класс ничего не
читает с диска — это просто данные.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PluginInfo:
    """Плагин, обнаруженный в папке плагинов."""

    name: str
    title: str = ""
    version: str = ""
    icon: str = "puzzle-piece"
    description: str = ""
    order: int = 900
    enabled: bool = True
    #: Есть ли в папке плагина схема настроек (`settings.json`).
    has_settings: bool = False
    #: Имя файла схемы внутри папки плагина.
    settings_file: str = "settings.json"
    #: Абсолютный путь к папке плагина (для диагностики и удаления).
    path: Path | None = None
    #: Замечания сканера: битый манифест, отсутствующая схема и т.п.
    problems: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """Подпись плагина в интерфейсе."""
        return self.title or self.name