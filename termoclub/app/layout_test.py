# termoclub/app/layout_test.py
"""Тесты каркаса: геометрия рабочей области и видимость боковых панелей."""
from __future__ import annotations

import flet as ft

from app.layout import (
    CONTENT_MIN_WIDTH,
    MAX_PANEL_WIDTH,
    MIN_PANEL_WIDTH,
    RESIZE_HANDLE_WIDTH,
    ApplicationLayout,
    CollapsiblePanel,
    PanelConfig,
)


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
    """Из размера окна вычитаются боковые панели, тумблеры, полосы тяги и верх/низ."""
    layout = ApplicationLayout(_StubPage(), _expanded())  # type: ignore[arg-type]
    width, height = layout.workspace_area_size(1400, 900)
    side = (
        280
        + 280
        + 2 * CollapsiblePanel.TOGGLE_WIDTH
        + 2 * RESIZE_HANDLE_WIDTH
    )
    assert width == 1400 - side
    assert height == 900 - 40 - 28


def test_collapsed_panel_frees_its_width() -> None:
    """Свёрнутая панель занимает ноль: рабочая область шире."""
    layout = ApplicationLayout(_StubPage(), _expanded())  # type: ignore[arg-type]
    full, _ = layout.workspace_area_size(1400, 900)
    layout.set_panel_visible("right", False)
    collapsed, _ = layout.workspace_area_size(1400, 900)
    assert collapsed == full + PanelConfig().right_width + RESIZE_HANDLE_WIDTH


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


# --- Растягивание панелей мышью ---


class _Drag:
    """Событие перетаскивания: layout читает только `primary_delta`."""

    def __init__(self, delta: float) -> None:
        self.primary_delta = delta


def test_drag_grows_and_shrinks_a_panel() -> None:
    """Перетаскивание полосы меняет ширину панели."""
    panel = CollapsiblePanel(_StubPage(), "left", 280, collapsed=False)  # type: ignore[arg-type]
    panel._on_drag_update(_Drag(40))
    assert panel.current_width == 320
    panel._on_drag_update(_Drag(-50))
    assert panel.current_width == 270


def test_drag_cannot_exceed_the_configured_maximum() -> None:
    """Настройка максимальной ширины держит верхнюю границу при тяге."""
    panel = CollapsiblePanel(  # type: ignore[arg-type]
        _StubPage(), "left", 280, collapsed=False, max_width=400
    )
    panel._on_drag_update(_Drag(10_000))
    assert panel.current_width == 400


def test_drag_cannot_shrink_below_the_minimum() -> None:
    """Ниже общего минимума панель не сужается: там текст нечитаем."""
    panel = CollapsiblePanel(_StubPage(), "left", 280, collapsed=False)  # type: ignore[arg-type]
    panel._on_drag_update(_Drag(-10_000))
    assert panel.current_width == MIN_PANEL_WIDTH


def test_right_panel_grows_when_dragged_left() -> None:
    """У правой панели внутренний край уходит влево — тяга налево её расширяет."""
    panel = CollapsiblePanel(_StubPage(), "right", 280, collapsed=False)  # type: ignore[arg-type]
    panel._on_drag_update(_Drag(-40))
    assert panel.current_width == 320


def test_panel_limits_are_separate_for_left_and_right() -> None:
    """Пределы ширины левой и правой панелей задаются отдельно."""
    config = PanelConfig(max_left_width=300, max_right_width=500)
    layout = ApplicationLayout(_StubPage(), config)  # type: ignore[arg-type]
    # Левая растёт от тяги вправо, правая — от тяги влево (знак дельты).
    layout.left_panel._on_drag_update(_Drag(10_000))
    layout.right_panel._on_drag_update(_Drag(-10_000))
    assert layout.panel_widths() == (300, 500)


def test_lower_max_width_pulls_a_wider_panel_in() -> None:
    """Уменьшение настройки подтягивает уже раскрытую панель.

    Иначе настройка запрещала бы ширину, которую панель продолжает
    показывать.
    """
    panel = CollapsiblePanel(  # type: ignore[arg-type]
        _StubPage(), "left", 280, collapsed=False, max_width=600
    )
    panel.set_width(600)
    panel.set_max_width(250)
    assert panel.current_width == 250
    assert panel.panel.width == 250.0


def test_panel_width_is_reported_after_drag() -> None:
    """Итог перетаскивания уходит наружу: его сохраняют в состоянии окна."""
    seen: list[tuple[str, int]] = []
    panel = CollapsiblePanel(  # type: ignore[arg-type]
        _StubPage(),
        "left",
        280,
        collapsed=False,
        on_resize=lambda position, width: seen.append((position, width)),
    )
    panel._on_drag_update(_Drag(30))
    panel._on_drag_end(None)  # type: ignore[arg-type]
    assert seen[-1] == ("left", 310)


def test_workspace_area_follows_dragged_width() -> None:
    """Рабочая область пересчитывается по новой ширине панели.

    От этого числа зависит сетка терминала, поэтому тяга обязана попадать
    в геометрию, а не только в ширину контрола.
    """
    layout = ApplicationLayout(_StubPage(), _expanded())  # type: ignore[arg-type]
    before, _ = layout.workspace_area_size(1400, 900)
    layout.left_panel._on_drag_update(_Drag(100))
    after, _ = layout.workspace_area_size(1400, 900)
    assert before - after == 100


# --- Прокрутка панелей ---


def test_side_panels_scroll_in_both_directions() -> None:
    """У панелей есть и вертикальная, и горизонтальная прокрутка.

    Вертикальная — для длинных списков, горизонтальная — чтобы прочитать
    содержимое, когда панель сузили мышью.
    """
    panel = CollapsiblePanel(_StubPage(), "left", 280, collapsed=False)  # type: ignore[arg-type]
    assert panel._scroll.scroll == ft.ScrollMode.AUTO
    assert panel._content_host.scroll == ft.ScrollMode.AUTO


def test_narrow_panel_keeps_content_readable_instead_of_squeezing() -> None:
    """Суженная панель не сжимает содержимое уже читаемого минимума.

    Иначе текст переносится по символу и «разъезжается» по высоте.
    """
    panel = CollapsiblePanel(_StubPage(), "left", 280, collapsed=False)  # type: ignore[arg-type]
    panel.set_width(MIN_PANEL_WIDTH)
    assert panel.current_width == MIN_PANEL_WIDTH
    assert panel._content_holder.width == CONTENT_MIN_WIDTH


def test_wide_panel_content_fills_the_panel() -> None:
    """Пока панель шире минимума, содержимое занимает её целиком."""
    panel = CollapsiblePanel(  # type: ignore[arg-type]
        _StubPage(), "left", 280, collapsed=False, max_width=MAX_PANEL_WIDTH
    )
    panel.set_width(500)
    assert panel._content_holder.width == 500.0
