# termoclub/app/ui/components_test.py
"""Тесты переиспользуемых UI-компонентов и единого формата результата."""
from __future__ import annotations

import flet as ft

from app.ui.components import show_snack
from core.result import Result


def test_result_success() -> None:
    """Успешный Result имеет ok=True."""
    r = Result.success("done")
    assert r.ok is True
    assert r.message == "done"


def test_result_failure() -> None:
    """Ошибочный Result имеет ok=False и сообщение."""
    r = Result.failure("boom")
    assert r.ok is False
    assert r.message == "boom"


class _StubPage:
    """Страница-заглушка: запоминает то, что получил `show_dialog`.

    Во Flet 1.0 у `Page` нет поля `snack_bar`, и `show_dialog(DialogControl)` —
    единственный вход для уведомления. Заглушка повторяет именно этот контракт,
    а не внутренний стек диалогов настоящей страницы.
    """

    def __init__(self) -> None:
        self.shown_dialogs: list = []

    def show_dialog(self, dialog) -> None:  # type: ignore[no-untyped-def]
        self.shown_dialogs.append(dialog)


def test_show_snack_uses_show_dialog() -> None:
    """Уведомление уходит в `Page.show_dialog` и является `DialogControl`."""
    page = _StubPage()
    show_snack(page, "Settings saved")

    assert len(page.shown_dialogs) == 1
    snack = page.shown_dialogs[0]
    assert isinstance(snack, ft.SnackBar)
    assert isinstance(snack, ft.DialogControl)  # тип, который принимает show_dialog


def test_show_snack_marks_errors() -> None:
    """Ошибка подсвечивается, обычное сообщение показывается нейтрально."""
    page = _StubPage()
    show_snack(page, "boom", is_error=True)
    error_snack = page.shown_dialogs[0]
    assert error_snack.bgcolor is not None
    assert isinstance(error_snack.content, ft.Text)
    assert error_snack.content.color is not None

    plain = _StubPage()
    show_snack(plain, "ok")
    assert plain.shown_dialogs[0].bgcolor is None
    assert plain.shown_dialogs[0].content.color is None
