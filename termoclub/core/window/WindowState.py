# termoclub/core/window/WindowState.py
"""Снимок состояния главного окна для сохранения между запусками.

Значимая часть — размер окна и то, какие выдвижные панели раскрыты. Список
открытых вкладок зарезервирован (`tabs`): поле участвует в сериализации и
переживёт запись/чтение, но приложение его пока не заполняет — восстановление
вкладок будет отдельной задачей.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Нижние границы размера окна: уже/ниже восстанавливать нечего.
MIN_WIDTH = 640
MIN_HEIGHT = 400

#: Размер окна по умолчанию, когда сохранённого состояния ещё нет.
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800


def _positive_int(value: Any, fallback: int, minimum: int) -> int:
    """Приводит значение к целому размеру не меньше `minimum`.

    Файл состояния — обычный JSON в профиле: его может испортить правка
    руками или запись предыдущей версии, поэтому любое неподходящее значение
    заменяется умолчанием, а не роняет запуск.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return number if number >= minimum else fallback


def _flag(value: Any, fallback: bool) -> bool:
    """Читает булев флаг, принимая и `true/false`, и `0/1`."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return fallback


def _optional_width(value: Any) -> int:
    """Читает сохранённую ширину панели; 0 — «ширина не задана».

    Ноль означает «пользователь ширину не тянул»: тогда панель открывается
    на ширину по умолчанию. Ограничения проверяет сам layout, здесь важно
    лишь отбросить мусор из файла.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return number if number > 0 else 0


@dataclass
class WindowState:
    """Состояние главного окна: геометрия и раскрытые панели."""

    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    maximized: bool = False
    left_panel_open: bool = False
    right_panel_open: bool = False
    #: Ширина панелей, выставленная перетаскиванием (0 — не трогали).
    left_panel_width: int = 0
    right_panel_width: int = 0
    #: Зарезервировано под восстановление вкладок (отдельная задача).
    tabs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Представление для JSON-файла профиля."""
        return {
            "width": self.width,
            "height": self.height,
            "maximized": self.maximized,
            "left_panel_open": self.left_panel_open,
            "right_panel_open": self.right_panel_open,
            "left_panel_width": self.left_panel_width,
            "right_panel_width": self.right_panel_width,
            "tabs": list(self.tabs),
        }

    @classmethod
    def from_dict(cls, payload: Any, fallback: "WindowState | None" = None) -> "WindowState":
        """Собирает состояние из словаря, чиня каждое поле отдельно.

        `fallback` — состояние для недостающих полей (обычно умолчания);
        он же страхует случай, когда на входе вообще не словарь.
        """
        base = fallback or cls()
        if not isinstance(payload, dict):
            return base
        return cls(
            width=_positive_int(payload.get("width"), base.width, MIN_WIDTH),
            height=_positive_int(payload.get("height"), base.height, MIN_HEIGHT),
            maximized=_flag(payload.get("maximized"), base.maximized),
            left_panel_open=_flag(payload.get("left_panel_open"), base.left_panel_open),
            right_panel_open=_flag(payload.get("right_panel_open"), base.right_panel_open),
            left_panel_width=_optional_width(payload.get("left_panel_width")),
            right_panel_width=_optional_width(payload.get("right_panel_width")),
            tabs=_tab_list(payload.get("tabs")),
        )


def _tab_list(value: Any) -> list[dict[str, Any]]:
    """Оставляет только словари-описания вкладок.

    Поле пока не заполняется приложением, но если в файле окажется мусор
    (строка, числа), он не должен попадать дальше в UI.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]