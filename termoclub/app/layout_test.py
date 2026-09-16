# termoclub/app/layout_test.py
"""Тесты геометрии каркаса: размер рабочей области для терминала."""
from __future__ import annotations

from app.layout import ApplicationLayout, CollapsiblePanel, PanelConfig


class _StubPage:
    """Страница-заглушка: layout использует её только для обновлений."""

    def update(self) -> None:
        pass


def test_workspace_area_subtracts_panels_and_toggles() -> None:
    """Из размера окна вычитаются боковые панели, тумблеры и верх/низ."""
    layout = ApplicationLayout(_StubPage(), PanelConfig())  # type: ignore[arg-type]
    width, height = layout.workspace_area_size(1400, 900)
    side = 280 + 280 + 2 * CollapsiblePanel.TOGGLE_WIDTH
    assert width == 1400 - side
    assert height == 900 - 40 - 28


def test_collapsed_panels_free_their_width() -> None:
    """Свёрнутая панель занимает ноль: рабочая область шире."""
    layout = ApplicationLayout(_StubPage(), PanelConfig())  # type: ignore[arg-type]
    full, _ = layout.workspace_area_size(1400, 900)
    layout.right_panel.is_visible = False
    layout.right_panel.panel.width = 0.0
    collapsed, _ = layout.workspace_area_size(1400, 900)
    assert collapsed == full + PanelConfig().right_width


def test_tiny_window_does_not_go_negative() -> None:
    """Крошечное окно даёт нулевую область, а не отрицательный размер."""
    layout = ApplicationLayout(_StubPage(), PanelConfig())  # type: ignore[arg-type]
    assert layout.workspace_area_size(100, 20) == (0.0, 0.0)
