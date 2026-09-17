# termoclub/app/layout_test.py
"""Тесты каркаса: геометрия рабочей области и видимость боковых панелей."""
from __future__ import annotations

import flet as ft

from app.layout import ApplicationLayout, CollapsiblePanel, PanelConfig


class _StubPage:
    """Страница-заглушка: layout использует её только для обновлений."""

    def update(self) -> None:
        pass


def _expanded() -> PanelConfig:
    """Конфигурация с раскрытыми панелями: так считалась прежняя геометрия."""
    return PanelConfig(left_collapsed=False, right_collapsed=False)


def test_panels_are_collapsed_by_default() -> None:
    """При запуске обе выдвижные панели свёрнуты.

    Рабочая область шире, а раскрывает панель только тот, кому она нужна.
    """
    layout = ApplicationLayout(_StubPage(), PanelConfig())  # type: ignore[arg-type]
    assert layout.panel_visibility() == (False, False)
    assert layout.left_panel.panel.width == 0.0
    assert layout.right_panel.panel.width == 0.0


def test_collapsed_panel_starts_without_animation_frame() -> None:
    """Свёрнутая панель сразу имеет нулевую ширину и «закрытую» иконку.

    Если бы ширина выставлялась только при клике по тумблеру, первый кадр
    рисовался бы раскрытым, а затем панель уезжала бы в ноль.
    """
    panel = CollapsiblePanel(_StubPage(), "left", 280, collapsed=True)  # type: ignore[arg-type]
    assert panel.is_visible is False
    assert panel.panel.width == 0.0
    assert panel.toggle_button.content.icon == ft.Icons.CHEVRON_RIGHT


def test_workspace_area_subtracts_panels_and_toggles() -> None:
    """Из размера окна вычитаются боковые панели, тумблеры и верх/низ."""
    layout = ApplicationLayout(_StubPage(), _expanded())  # type: ignore[arg-type]
    width, height = layout.workspace_area_size(1400, 900)
    side = 280 + 280 + 2 * CollapsiblePanel.TOGGLE_WIDTH
    assert width == 1400 - side
    assert height == 900 - 40 - 28


def test_collapsed_panel_frees_its_width() -> None:
    """Свёрнутая панель занимает ноль: рабочая область шире."""
    layout = ApplicationLayout(_StubPage(), _expanded())  # type: ignore[arg-type]
    full, _ = layout.workspace_area_size(1400, 900)
    layout.set_panel_visible("right", False)
    collapsed, _ = layout.workspace_area_size(1400, 900)
    assert collapsed == full + PanelConfig().right_width


def test_set_panel_visible_notifies_only_on_request() -> None:
    """Программное применение состояния не уведомляет о переключении.

    Иначе восстановление сохранённого вида писало бы в файл то, что только
    что из него прочитано.
    """
    calls: list[tuple[str, bool]] = []
    layout = ApplicationLayout(
        _StubPage(),  # type: ignore[arg-type]
        PanelConfig(),
        on_panel_toggle=lambda position, visible: calls.append((position, visible)),
    )
    layout.set_panel_visible("left", True)
    assert layout.left_panel.is_visible is True
    assert calls == []

    layout.left_panel.set_visible(False, notify=True)
    assert calls == [("left", False)]


def test_tiny_window_does_not_go_negative() -> None:
    """Крошечное окно даёт нулевую область, а не отрицательный размер."""
    layout = ApplicationLayout(_StubPage(), _expanded())  # type: ignore[arg-type]
    assert layout.workspace_area_size(100, 20) == (0.0, 0.0)
