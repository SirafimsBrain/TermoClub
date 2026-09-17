# termoclub/app/ui/settings/LinkOpener.py
"""Открытие ссылок и работа с буфером обмена для настроек-ссылок.

Flet выполняет и то, и другое сервисами (`ft.UrlLauncher`, `ft.Clipboard`),
которые нужно зарегистрировать на странице, а вызовы у них асинхронные.
GUI-слой настроек не должен об этом знать, поэтому сервисы спрятаны здесь.

Недоступность сервиса не считается ошибкой приложения: метод возвращает
текст проблемы, и контрол показывает его пользователю.
"""
from __future__ import annotations

import logging

import flet as ft

logger = logging.getLogger(__name__)


class LinkOpener:
    """Открывает ссылки в системе и копирует их в буфер обмена."""

    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self._launcher: ft.UrlLauncher | None = None
        self._clipboard: ft.Clipboard | None = None

    async def open(self, url: str) -> str:
        """Открывает ссылку; возвращает текст ошибки или пустую строку."""
        if not url:
            return ""
        service = self._ensure_launcher()
        if service is None:
            return "Cannot open link: platform launcher is unavailable"
        try:
            await service.launch_url(url)
        except Exception as exc:  # noqa: BLE001 — зависит от платформы и схемы
            logger.warning("LinkOpener: cannot open %s: %s", url, exc)
            return f"Cannot open link: {exc}"
        return ""

    async def copy(self, text: str) -> str:
        """Копирует строку в буфер обмена; возвращает текст ошибки."""
        service = self._ensure_clipboard()
        if service is None:
            return "Cannot copy: clipboard is unavailable"
        try:
            await service.set(text)
        except Exception as exc:  # noqa: BLE001 — буфер есть не на всех платформах
            logger.warning("LinkOpener: cannot copy to clipboard: %s", exc)
            return f"Cannot copy: {exc}"
        return ""

    def _ensure_launcher(self) -> ft.UrlLauncher | None:
        """Создаёт сервис открытия ссылок один раз."""
        if self._launcher is not None:
            return self._launcher
        try:
            self._launcher = ft.UrlLauncher()
            self._page.services.append(self._launcher)
        except Exception as exc:  # noqa: BLE001 — сервис недоступен в этом режиме
            logger.warning("LinkOpener: launcher unavailable: %s", exc)
            return None
        return self._launcher

    def _ensure_clipboard(self) -> ft.Clipboard | None:
        """Создаёт сервис буфера обмена один раз."""
        if self._clipboard is not None:
            return self._clipboard
        try:
            self._clipboard = ft.Clipboard()
            self._page.services.append(self._clipboard)
        except Exception as exc:  # noqa: BLE001 — сервис недоступен в этом режиме
            logger.warning("LinkOpener: clipboard unavailable: %s", exc)
            return None
        return self._clipboard