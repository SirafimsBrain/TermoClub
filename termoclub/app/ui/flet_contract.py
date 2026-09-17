# termoclub/app/ui/flet_contract.py
"""Проверка контролов по контракту клиента Flet (для тестов и диагностики).

Flet валидирует состояние контрола перед отправкой на клиент
(`BaseControl._before_update_safe`) и сериализует его в msgpack. Оба шага
исполняются в Python, поэтому их можно прогнать без окна и без Dart — и
именно так ловятся состояния, на которых вкладка выглядела как серая
заглушка `ErrorWidget`:

* `SegmentedButton` без сегментов («segments must contain at least one
  visible Control») — так ломалась вкладка настроек;
* `set` в поле, которое клиент ждёт списком («can not serialize 'set'
  object»);
* `TextThemeStyle` в `Text.style` (клиент разбирает значение как map).

Проверка клиентской отрисовки тут невозможна: Dart-ошибку видно только в
живом окне. Поэтому проверяем ровно тот контракт, который готовит данные
для клиента.
"""
from __future__ import annotations

import msgpack

import flet as ft
from flet.controls.base_control import BaseControl
from flet.messaging.protocol import configure_encode_object_for_msgpack

#: Атрибуты, в которых Flet хранит вложенные контролы.
CHILD_ATTRIBUTES = (
    "controls",
    "content",
    "spans",
    "actions",
    "leading",
    "trailing",
    "items",
    "label",
)


def children(control: ft.Control) -> list[ft.Control]:
    """Вложенные контролы в порядке появления в дереве."""
    found: list[ft.Control] = []
    for name in CHILD_ATTRIBUTES:
        value = getattr(control, name, None)
        if isinstance(value, list):
            found.extend(item for item in value if isinstance(item, ft.Control))
        elif isinstance(value, ft.Control):
            found.append(value)
    return found


def _encode(control: ft.Control):  # type: ignore[no-untyped-def]
    """Кодек Flet для msgpack (тот же, что в транспорте клиента)."""
    return configure_encode_object_for_msgpack(BaseControl)(control)


def check_control(control: ft.Control) -> list[str]:
    """Прогоняет контрол через валидацию и сериализацию Flet.

    Возвращает список проблем: пустой список означает, что контрол можно
    отправлять клиенту.
    """
    problems: list[str] = []
    try:
        control._before_update_safe()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — нужен любой текст причины
        problems.append(f"validation {type(control).__name__}: {exc}")
    try:
        msgpack.packb(control, default=_encode)
    except Exception as exc:  # noqa: BLE001 — нужен любой текст причины
        problems.append(f"serialization {type(control).__name__}: {exc}")
    return problems


def check_tree(control: ft.Control, path: str = "root") -> list[str]:
    """Проверяет всё дерево контролов и возвращает пути с проблемами."""
    problems = [f"{path}: {problem}" for problem in check_control(control)]
    for index, child in enumerate(children(control)):
        problems.extend(check_tree(child, f"{path}/{index}:{type(child).__name__}"))
    return problems
