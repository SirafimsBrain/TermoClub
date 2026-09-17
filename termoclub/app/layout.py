# termoclub/app/layout.py
"""Five-panel main window layout (ported from Rhizome client).

Top panel, collapsible left panel, central workspace, collapsible
right panel, bottom status panel. Pure UI — knows nothing about
concrete terminals, works only with Flet controls.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import flet as ft


@dataclass
class PanelConfig:
    """Sizes of the five panels and their initial visibility."""

    left_width: int = 280
    right_width: int = 280
    top_height: int = 40
    bottom_height: int = 28
    #: Обе выдвижные панели при запуске свёрнуты: рабочая область шире,
    #: а пользователь раскрывает только ту, что нужна. Сохранённое состояние
    #: окна (см. `app/window`) может вернуть их открытыми.
    left_collapsed: bool = True
    right_collapsed: bool = True


class CollapsiblePanel:
    """Side panel with a sticky toggle button.

    Панель либо показана целиком (`default_width`), либо свёрнута в ноль —
    промежуточных ширин нет, потому что перетаскивания за край нет.
    """

    #: Ширина полосы с кнопкой-тумблером.
    TOGGLE_WIDTH = 16

    def __init__(
        self,
        page: ft.Page,
        position: str,
        default_width: int = 280,
        collapsed: bool = False,
        on_toggle: Callable[[str, bool], None] | None = None,
    ) -> None:
        self.page = page
        self.position = position
        self.default_width = default_width
        self.is_visible = not collapsed
        self._on_toggle = on_toggle

        is_left = position == "left"

        self.panel = ft.Container(
            width=float(self.default_width),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
            border=ft.Border(
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT) if is_left else ft.BorderSide(0),
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
                if not is_left
                else ft.BorderSide(0),
            ),
            content=None,
        )

        self.toggle_button = ft.Container(
            width=self.TOGGLE_WIDTH,
            content=ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT if is_left else ft.Icons.CHEVRON_RIGHT,
                icon_size=16,
                on_click=self._on_toggle_click,
                style=ft.ButtonStyle(padding=0),
            ),
            on_hover=self._on_hover,
            bgcolor=ft.Colors.TRANSPARENT,
        )
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        """Приводит ширину панели и иконку тумблера к `is_visible`.

        Вызывается и из конструктора: панель может создаваться свёрнутой,
        и тогда первый же кадр должен рисоваться в свёрнутом виде, без
        анимации «раскрыл и тут же закрыл».
        """
        is_left = self.position == "left"
        if self.is_visible:
            self.panel.width = float(self.default_width)
            self.toggle_button.content.icon = (
                ft.Icons.CHEVRON_LEFT if is_left else ft.Icons.CHEVRON_RIGHT
            )
        else:
            self.panel.width = 0.0
            self.toggle_button.content.icon = (
                ft.Icons.CHEVRON_RIGHT if is_left else ft.Icons.CHEVRON_LEFT
            )

    def set_visible(self, visible: bool, *, notify: bool = False) -> None:
        """Раскрывает или сворачивает панель.

        `notify` выключен для программного применения сохранённого состояния:
        там вызывающий сам решает, писать ли его на диск.
        """
        self.is_visible = visible
        self._sync_visibility()
        self.toggle_button.bgcolor = ft.Colors.TRANSPARENT
        self._update(self.panel, self.toggle_button)
        if notify and self._on_toggle is not None:
            self._on_toggle(self.position, self.is_visible)

    def _on_toggle_click(self, e: ft.ControlEvent) -> None:
        self.set_visible(not self.is_visible, notify=True)

    def _on_hover(self, e: ft.ControlEvent) -> None:
        if e.data == "true":
            self.toggle_button.bgcolor = ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)
        else:
            self.toggle_button.bgcolor = ft.Colors.TRANSPARENT
        self._update(self.toggle_button)

    def _update(self, *controls: ft.Control) -> None:
        """Перерисовывает только свои контролы, а не всю страницу.

        `page.update()` на каждое событие перестраивал всё окно, включая
        терминал; во время анимации панели (300 мс) это накладывалось на
        изменение ширины рабочей области и давало рваную перерисовку.
        """
        for control in controls:
            try:
                control.update()
            except RuntimeError:
                pass  # Ещё не примонтирован к странице.

    def set_content(self, content: ft.Control) -> None:
        self.panel.content = content
        self._update(self.panel)


class ApplicationLayout:
    """5-panel layout: top, left (collapsible), workspace (center), right (collapsible), bottom."""

    def __init__(
        self,
        page: ft.Page,
        config: PanelConfig | None = None,
        on_panel_toggle: Callable[[str, bool], None] | None = None,
    ) -> None:
        self.page = page
        self.config = config or PanelConfig()

        self.top_panel = ft.Container(
            height=float(self.config.top_height),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            content=ft.Row([], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        )

        self.bottom_panel = ft.Container(
            height=float(self.config.bottom_height),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            content=ft.Row([], alignment=ft.MainAxisAlignment.START),
        )

        self.left_panel = CollapsiblePanel(
            page,
            position="left",
            default_width=self.config.left_width,
            collapsed=self.config.left_collapsed,
            on_toggle=on_panel_toggle,
        )
        self.right_panel = CollapsiblePanel(
            page,
            position="right",
            default_width=self.config.right_width,
            collapsed=self.config.right_collapsed,
            on_toggle=on_panel_toggle,
        )

        self.workspace_panel = ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                [ft.Text("Workspace")],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def build(self) -> ft.Control:
        middle_section = ft.Row(
            [
                self.left_panel.panel,
                self.left_panel.toggle_button,
                self.workspace_panel,
                self.right_panel.toggle_button,
                self.right_panel.panel,
            ],
            spacing=0,
            expand=True,
        )
        return ft.Column(
            [
                self.top_panel,
                ft.Container(content=middle_section, expand=True),
                self.bottom_panel,
            ],
            spacing=0,
            expand=True,
        )

    def workspace_area_size(self, width: float, height: float) -> tuple[float, float]:
        """Размер центральной рабочей области в пикселях для размера окна.

        Нужен терминалу: скрытая вкладка не получает `on_size_change`, а при
        показе новый кадр может не прийти вовсе, поэтому сетку нужно уметь
        пересчитать из размера страницы. Геометрия известна только здесь:
        две боковые панели (свёрнутая занимает ноль) и по полосе тумблера
        на каждую, плюс верхняя и нижняя панели по высоте.
        """
        side = 0.0
        for panel in (self.left_panel, self.right_panel):
            side += CollapsiblePanel.TOGGLE_WIDTH
            if panel.is_visible:
                panel_width = panel.panel.width
                if panel_width is None:
                    panel_width = float(panel.default_width)
                side += float(panel_width)
        return max(width - side, 0.0), max(
            height - self.config.top_height - self.config.bottom_height, 0.0
        )

    def set_top_content(self, content: ft.Control) -> None:
        self.top_panel.content = content
        self._safe_update(self.top_panel)

    def set_bottom_content(self, content: ft.Control) -> None:
        self.bottom_panel.content = content
        self._safe_update(self.bottom_panel)

    def set_left_content(self, content: ft.Control) -> None:
        self.left_panel.set_content(content)

    def set_right_content(self, content: ft.Control) -> None:
        self.right_panel.set_content(content)

    def set_panel_visible(self, position: str, visible: bool) -> None:
        """Программно раскрывает/сворачивает панель без уведомления наружу.

        Нужно при восстановлении сохранённого состояния окна: снимок уже
        прочитан с диска, и снова его писать (и слать уведомление) не надо.
        """
        panel = self.left_panel if position == "left" else self.right_panel
        panel.set_visible(visible, notify=False)

    def panel_visibility(self) -> tuple[bool, bool]:
        """Текущая видимость боковых панелей (лев, прав)."""
        return self.left_panel.is_visible, self.right_panel.is_visible

    def set_workspace_content(self, content: ft.Control) -> None:
        self.workspace_panel.content = content
        self._safe_update(self.workspace_panel)

    @staticmethod
    def _safe_update(control: ft.Control) -> None:
        try:
            control.update()
        except RuntimeError:
            pass  # Ещё не примонтирован к странице.
