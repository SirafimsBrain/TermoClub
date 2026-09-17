# termoclub/core/sessions/terminal/ScreenModel.py
"""Модель экрана терминала на основе pyte.

Предоставляет pyte Screen через удобный интерфейс для Flet:
- Обновление контента при изменении экрана
- Получение текста для отображения
- Обработка resize
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import pyte

logger = logging.getLogger(__name__)


class ScreenModel:
    """Обёртка над pyte Screen для работы с Flet.

    Содержит экземпляр pyte.Screen и pyte.ByteStream для
    обработки ANSI-последовательностей. Предоставляет
    текстовое представление экрана и информацию о курсоре.
    """

    def __init__(self, cols: int = 80, rows: int = 24) -> None:
        self._cols = cols
        self._rows = rows
        self._screen = pyte.Screen(cols, rows)
        self._stream = pyte.ByteStream(self._screen)
        self._on_change: Optional[Callable[[], None]] = None

    @property
    def screen(self) -> pyte.Screen:
        """Возвращает pyte Screen."""
        return self._screen

    @property
    def cols(self) -> int:
        """Текущее количество колонок."""
        return self._cols

    @property
    def rows(self) -> int:
        """Текущее количество строк."""
        return self._rows

    def feed(self, data: bytes) -> None:
        """Обрабатывает входные байты через pyte ByteStream.

        :param data: Байты ANSI-последовательностей или текста.
        """
        try:
            self._stream.feed(data)
            if self._on_change:
                self._on_change()
        except Exception as e:
            logger.error("ScreenModel.feed: %s", e)

    def feed_text(self, text: str) -> None:
        """Обрабатывает текстовую строку.

        :param text: Текст для отображения на экране.
        """
        self.feed(text.encode('utf-8'))

    def get_text(self) -> str:
        """Возвращает текстовое представление экрана.

        :return: Строка с отображаемым содержимым экрана.
        """
        return self._screen.display

    def get_cursor_position(self) -> tuple[int, int]:
        """Возвращает позицию курсора (y, x).

        :return: Кортеж (строка, колонка) курсора.
        """
        return (self._screen.cursor.y, self._screen.cursor.x)

    def resize(self, cols: int, rows: int) -> None:
        """Изменяет размер экрана.

        :param cols: Новое количество колонок.
        :param rows: Новое количество строк.
        """
        self._cols = cols
        self._rows = rows
        self._screen.resize(rows, cols)
        logger.info("ScreenModel: resized to %dx%d", cols, rows)

    @property
    def on_change(self) -> Optional[Callable[[], None]]:
        """Callback, вызываемый при изменении экрана."""
        return self._on_change

    @on_change.setter
    def on_change(self, callback: Optional[Callable[[], None]]) -> None:
        """Устанавливает callback для уведомления об изменениях экрана."""
        self._on_change = callback

    def clear(self) -> None:
        """Очищает экран."""
        self._screen.reset()
        if self._on_change:
            self._on_change()

    def content_hash(self) -> int:
        """Вычисляет хеш текущего содержимого экрана.

        Используется для проверки стабильности экрана
        (не изменилось ли содержимое с последнего вызова).

        :return: Хеш содержимого экрана.
        """
        # Используем отображаемый текст для хеширования
        # (без учёта курсора и атрибутов)
        content = self._screen.display
        return hash(content)