# termoclub/core/settings/SettingsApplier.py
"""Применение настроек к уже работающим частям приложения.

Настройки из файла мало сохранить: часть из них влияет на то, что уже
работает — тема окна, уровень логирования, активный терминал, шрифт и
цвета открытых вкладок терминала. Схема помечает такие настройки полем
`applier`, а этот класс превращает имя applier'а в конкретное действие.

Класс не знает про Flet-разметку: он получает «поставщиков» страницы и
живых сессий от UI-слоя (`register_page`, `register_sessions`) и работает
с ними через минимальный контракт (`theme_mode`, `apply_appearance`, ...).
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

from core.config import DEFAULT_TERMINAL
from core.result import Result
from core.settings.SettingsError import SettingsError
from core.settings.SettingsStore import SettingsStore

logger = logging.getLogger(__name__)


class SettingsApplier:
    """Применяет изменения настроек к живым компонентам приложения."""

    def __init__(
        self,
        store: SettingsStore,
        sessions: Callable[[], Iterable[Any]] | None = None,
        page: Any | None = None,
        terminal_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._store = store
        self._sessions = sessions
        self._page = page
        self._terminal_factory = terminal_factory
        #: Имя applier'а -> метод класса (расширяемо без правки схемы).
        #: Обработчик получает slug категории и новое значение: категория
        #: нужна там, где менять надо только «свои» вкладки терминала.
        self._handlers: dict[str, Callable[[str, Any], None]] = {
            "theme_mode": self._apply_theme_mode,
            "theme_seed": self._apply_theme_seed,
            "log_level": self._apply_log_level,
            "active_terminal": self._apply_active_terminal,
            "terminal_appearance": self._apply_terminal_appearance,
            "terminal_refresh": self._apply_terminal_refresh,
        }

    # --- Регистрация «живых» целей ---

    def register_page(self, page: Any) -> None:
        """Запоминает страницу приложения (тема, шрифт интерфейса)."""
        self._page = page

    def register_sessions(self, provider: Callable[[], Iterable[Any]]) -> None:
        """Запоминает поставщика живых сессий (вкладок терминала)."""
        self._sessions = provider

    def register_terminal_factory(self, factory: Callable[[str], Any]) -> None:
        """Запоминает фабрику контроллеров внешнего терминала."""
        self._terminal_factory = factory

    # --- Применение ---

    def apply_all(self) -> list[str]:
        """Применяет все настройки, у которых задан applier."""
        applied: list[str] = []
        for category in self._store.categories:
            for spec in category.settings:
                if spec.applier and self.apply_spec(category.slug, spec.key, spec.applier):
                    applied.append(f"{category.slug}.{spec.key}")
        return applied

    def apply_category(self, slug: str) -> list[str]:
        """Применяет все applier'ы одной категории."""
        category = self._store.schema.require(slug)
        applied: list[str] = []
        for spec in category.settings:
            if spec.applier and self.apply_spec(slug, spec.key, spec.applier):
                applied.append(f"{slug}.{spec.key}")
        return applied

    def apply_spec(self, slug: str, key: str, applier: str) -> bool:
        """Применяет одну настройку; True — обработчик найден и вызван."""
        handler = self._handlers.get(applier)
        if handler is None:
            logger.warning("SettingsApplier: unknown applier %r (%s.%s)", applier, slug, key)
            return False
        try:
            handler(slug, self._store.get(slug, key))
        except Exception:  # noqa: BLE001 — настройка не должна ронять приложение
            logger.exception("SettingsApplier: %s.%s failed", slug, key)
            return False
        return True

    def apply_key(self, slug: str, key: str) -> bool:
        """Применяет одну настройку по ключу (без имени applier'а).

        Этим входом пользуется подписка на изменения хранилища: GUI знает
        только *что* поменялось, а имя обработчика берётся из схемы.
        """
        category = self._store.schema.find(slug)
        if category is None:
            return False
        spec = category.spec(key)
        if spec is None or not spec.applier:
            return False
        return self.apply_spec(slug, key, spec.applier)

    # --- Обработчики ---

    def _apply_theme_mode(self, slug: str, value: str) -> None:
        """Тема окна: light / dark / system."""
        if self._page is None:
            return
        self._page.theme_mode = _theme_mode(value)
        _safe_update(self._page)

    def _apply_theme_seed(self, slug: str, value: str) -> None:
        """Базовый цвет темы Material."""
        if self._page is None:
            return
        theme = self._page.theme
        if theme is None:
            return
        theme.color_scheme_seed = value or None
        _safe_update(self._page)

    def _apply_log_level(self, slug: str, value: str) -> None:
        """Уровень логирования централизованного логгера."""
        level = logging.getLevelNamesMapping().get(str(value).upper())
        if level is None:
            logger.warning("SettingsApplier: unknown log level %r", value)
            return
        logging.getLogger().setLevel(level)
        logger.info("SettingsApplier: log level set to %s", value)

    def _apply_active_terminal(self, slug: str, value: str) -> None:
        """Активный внешний терминал берётся фабрикой из окружения."""
        if value and self._terminal_factory is not None:
            controller = self._terminal_factory(value)
            result = controller.focus()
            if isinstance(result, Result) and not result.ok:
                logger.info("SettingsApplier: terminal %r focus: %s", value, result.message)
        logger.info(
            "SettingsApplier: active terminal %r selected (default %r)",
            value,
            DEFAULT_TERMINAL,
        )

    def _apply_terminal_appearance(self, slug: str, value: Any) -> None:
        """Шрифт, цвета и отступы применяются к вкладкам этой категории.

        Меняется только категория, чья настройка изменилась: у pyte и
        smartcli свои цвета и шрифты, и правка одной не должна переписывать
        внешний вид вкладок другого рендерера.
        """
        for session in self._live_sessions(category=slug):
            apply = getattr(session, "apply_appearance", None)
            if apply is not None:
                apply(self._store.values(slug))

    def _apply_terminal_refresh(self, slug: str, value: Any) -> None:
        """Частота перерисовки экрана активных вкладок."""
        for session in self._live_sessions(category=slug):
            apply = getattr(session, "apply_refresh_rate", None)
            if apply is not None:
                apply(int(value))

    def _live_sessions(self, category: str = "") -> list[Any]:
        """Живые сессии рабочей области (пусто, если источник не задан).

        Если задана `category`, остаются только сессии, объявившие её своей
        (`appearance_category`): так настройки терминала не «протекают» в
        вкладки другого рендерера, а сессии без категории пропускаются.
        """
        if self._sessions is None:
            return []
        try:
            sessions = list(self._sessions())
        except Exception:  # noqa: BLE001 — источник состояния не должен ломать настройки
            logger.exception("SettingsApplier: cannot enumerate sessions")
            return []
        if not category:
            return sessions
        return [
            session
            for session in sessions
            if getattr(session, "appearance_category", "") == category
        ]


def _theme_mode(value: str) -> Any:
    """Строка схемы -> `flet.ThemeMode` (без импорта Flet в тестах модели)."""
    import flet as ft

    try:
        return ft.ThemeMode(value)
    except ValueError:
        raise SettingsError(f"unknown theme mode: {value!r}") from None


def _safe_update(control: Any) -> None:
    """Обновляет контрол, если он уже примонтирован к странице."""
    update = getattr(control, "update", None)
    if update is None:
        return
    try:
        update()
    except RuntimeError:
        pass  # Ещё не примонтирован к странице.