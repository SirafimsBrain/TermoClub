# termoclub/app/ui/theme_style_test.py
"""Регрессия: `TextThemeStyle` передаётся только в `theme_style`.

Во Flet `Text.style` — это `TextStyle`, а клиент разбирает значение как map
(`value["weight"]`, `value["size"]`, ...). Enum `TextThemeStyle` сериализуется
строкой (`"titleLarge"`), поэтому Dart падал на сборке виджета
(`NoSuchMethodError`: у `String` нет `operator []`) и на месте контрола
рисовалась серая заглушка `ErrorWidget` — в release это `#C0C0C0` на всю
доступную область. Именно так выглядела пустая серая вкладка Settings.

Из Python клиентскую ошибку не видно (валидация Flet такое значение
пропускает, а msgpack сериализуется без ошибок), поэтому проверка статическая:
ищем использование `TextThemeStyle` в аргументе `style`.
"""
from __future__ import annotations

import re
from pathlib import Path

#: Корень пакета приложения (каталог `termoclub`).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: `style=ft.TextThemeStyle.X` (и `style = ft.TextThemeStyle`).
BAD_STYLE_ARGUMENT = re.compile(r"\bstyle\s*=\s*ft\.TextThemeStyle\b")


def _python_sources() -> list[Path]:
    """Все Python-файлы приложения, кроме самого этого теста.

    Исключение обязательно: в этом файле шаблон встречается в тексте самой
    проверки.
    """
    return [
        path
        for path in sorted(PROJECT_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
        and "assets" not in path.parts
        and path.name != Path(__file__).name
    ]


def test_text_theme_style_is_not_passed_to_style() -> None:
    """`TextThemeStyle` допустим только в `theme_style`, не в `style`."""
    offenders: list[str] = []
    for path in _python_sources():
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if BAD_STYLE_ARGUMENT.search(line):
                relative = path.relative_to(PROJECT_ROOT)
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert not offenders, (
        "TextThemeStyle передан в Text.style — клиент упадёт и нарисует серую "
        "заглушку ErrorWidget. Замените style= на theme_style=:\n"
        + "\n".join(offenders)
    )


def test_pattern_matches_only_the_bad_argument() -> None:
    """Проверка не вырождена: правило срабатывает именно на `style=`."""
    good = "ft.Text('x', theme_style=" + "ft.TextThemeStyle.TITLE_LARGE)"
    bad = "ft.Text('x', style=" + "ft.TextThemeStyle.TITLE_LARGE)"
    assert BAD_STYLE_ARGUMENT.search(good) is None
    assert BAD_STYLE_ARGUMENT.search(bad) is not None


def test_sources_are_scanned() -> None:
    """Сканирование действительно что-то находит (путь не сломан)."""
    names = {path.name for path in _python_sources()}
    assert {"settings.py", "logs.py", "home.py"} <= names
