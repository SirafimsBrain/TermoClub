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


#: Пределы ширины выдвижных панелей по умолчанию (пиксели).
MIN_PANEL_WIDTH = 160
MAX_PANEL_WIDTH = 600

#: Ширина полосы, за которую панель тянут мышью.
RESIZE_HANDLE_WIDTH = 6

#: Наименьшая ширина, при которой содержимое панели остаётся читаемым.
#: Уже этой ширины панель показывает горизонтальную прокрутку.
CONTENT_MIN_WIDTH = 240


@dataclass
class PanelConfig:
    """Sizes of the five panels and their initial visibility."""

    left_width: int = 280
    right_width: int = 280
    top_height: int = 40
    bottom_height: int = 28
    #: Обе выдвижные панели при запуске свёрнуты: рабочая область шире,
    #: а пользователь раскрывает только ту, что нужна. Сохранённое состояние
    #: окна (см. `core/window`) может вернуть их открытыми.
    left_collapsed: bool = True
    right_collapsed: bool = True
    #: Границы ширины выдвижных панелей. Нижняя — общая и задаёт предел, за
    #: которым содержимое перестаёт быть читаемым; верхние приходят из
    #: настроек (`appearance.left_panel_max_width` / `..._right_...`).
    min_panel_width: int = MIN_PANEL_WIDTH
    max_left_width: int = MAX_PANEL_WIDTH
    max_right_width: int = MAX_PANEL_WIDTH


class CollapsiblePanel:
    """Side panel with a sticky toggle button and a mouse-resizable width.

    Панель либо показана целиком (своя ширина), либо свёрнута в ноль.
    Раскрытая ширину можно тянуть за полосу у внутреннего края; предел
    сверху приходит из настроек (`max_width`), снизу — общий минимум,
    за которым содержимое перестаёт быть читаемым.
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
        min_width: int = MIN_PANEL_WIDTH,
        max_width: int = MAX_PANEL_WIDTH,
        on_resize: Callable[[str, int], None] | None = None,
    ) -> None:
        self.page = page
        self.position = position
        self.default_width = default_width
        self.min_width = min_width
        self.max_width = max(max_width, min_width)
        self.is_visible = not collapsed
        self._on_toggle = on_toggle
        self._on_resize = on_resize
        #: Текущая ширина раскрытой панели. Меняется перетаскиванием и
        #: ограничена парой `min_width`/`max_width`.
        self.current_width = self._clamp(default_width)

        is_left = position == "left"

        # Содержимое прокручивается в обе стороны, и это две вложенные
        # прокрутки: `Row` с горизонтальной держит `Column` с вертикальной.
        # Одна колонка обе оси не умеет, а вложенность здесь безопасна, пока
        # у внутреннего контрола есть конкретная ширина: раскрывающийся
        # контрол внутри прокручиваемой области получает бесконечные
        # ограничения по своей оси, и Flutter их не принимает.
        #
        # Ширина содержимого — максимум из ширины панели и читаемого
        # минимума. Пока панель шире минимума, прокрутки по горизонтали нет
        # и содержимое занимает всю панель; как только её сузили мышью ниже
        # минимума, содержимое перестаёт сжиматься и появляется прокрутка.
        self._content_host = ft.Column(
            [],
            spacing=0,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        )
        self._content_holder = ft.Container(content=self._content_host)
        self._scroll = ft.Row(
            [self._content_holder],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        self._sync_content_width()

        self.panel = ft.Container(
            width=float(self.current_width),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
            border=ft.Border(
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT) if is_left else ft.BorderSide(0),
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
                if not is_left
                else ft.BorderSide(0),
            ),
            content=self._scroll,
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

        # Полоса перетаскивания — у внутреннего края панели, рядом с рабочей
        # областью: за неё меняют ширину, и курсор это показывает.
        self.resize_handle = ft.GestureDetector(
            content=ft.Container(
                width=RESIZE_HANDLE_WIDTH,
                bgcolor=ft.Colors.TRANSPARENT,
            ),
            mouse_cursor=ft.MouseCursor.RESIZE_COLUMN,
            on_horizontal_drag_update=self._on_drag_update,
            on_horizontal_drag_end=self._on_drag_end,
        )
        #: Полоса живёт только у раскрытой панели.
        self.resize_handle.visible = self.is_visible
        self._sync_visibility()

    # --- Ширина ---

    def _clamp(self, width: float) -> int:
        """Приводит ширину в разрешённый диапазон."""
        return int(max(self.min_width, min(self.max_width, width)))

    def _content_width(self) -> int:
        """Ширина содержимого: не уже читаемого минимума.

        Пока панель шире `CONTENT_MIN_WIDTH`, содержимое занимает её целиком
        и горизонтальной прокрутки нет; ниже — содержимое держит минимум, и
        прокрутка появляется.
        """
        return max(self.current_width, CONTENT_MIN_WIDTH)

    def _sync_content_width(self) -> None:
        """Подгоняет ширину содержимого под текущую ширину панели."""
        self._content_holder.width = float(self._content_width())

    @property
    def max_width_setting(self) -> int:
        """Текущий верхний предел ширины (приходит из настроек)."""
        return self.max_width

    def set_max_width(self, max_width: int) -> None:
        """Меняет верхний предел ширины (настройка изменилась на лету).

        Заодно подтягивает саму панель: если она была шире нового предела,
        оставлять её такой — значит показывать то, что настройкой запрещено.
        """
        self.max_width = max(int(max_width), self.min_width)
        self.set_width(self.current_width)

    def set_width(self, width: float, *, notify: bool = False) -> None:
        """Задаёт ширину раскрытой панели с ограничением по пределам."""
        self.current_width = self._clamp(width)
        self._sync_visibility()
        self._update(self.panel, self.resize_handle, self._content_holder)
        if notify and self._on_resize is not None:
            self._on_resize(self.position, self.current_width)

    def _on_drag_update(self, event: ft.DragUpdateEvent) -> None:
        """Тянет ширину за полосу.

        `primary_delta` — смещение по основной оси жеста за кадр. Для правой
        панели знак обратный: её внутренний край уходит влево, когда ширина
        растёт.
        """
        delta = float(getattr(event, "primary_delta", 0) or 0)
        if self.position == "right":
            delta = -delta
        self.set_width(self.current_width + delta)

    def _on_drag_end(self, _event: ft.DragEndEvent) -> None:
        """Перетаскивание закончилось: фиксируем ширину для состояния окна."""
        if self._on_resize is not None:
            self._on_resize(self.position, self.current_width)

    # --- Видимость ---

    def _sync_visibility(self) -> None:
        """Приводит ширину панели и иконку тумблера к `is_visible`.

        Вызывается и из конструктора: панель может создаваться свёрнутой,
        и тогда первый же кадр должен рисоваться в свёрнутом виде, без
        анимации «раскрыл и тут же закрыл».
        """
        is_left = self.position == "left"
        if self.is_visible:
            self.panel.width = float(self.current_width)
            self.toggle_button.content.icon = (
                ft.Icons.CHEVRON_LEFT if is_left else ft.Icons.CHEVRON_RIGHT
            )
        else:
            self.panel.width = 0.0
            self.toggle_button.content.icon = (
                ft.Icons.CHEVRON_RIGHT if is_left else ft.Icons.CHEVRON_LEFT
            )
        self.resize_handle.visible = self.is_visible
        self._sync_content_width()

    def set_visible(self, visible: bool, *, notify: bool = False) -> None:
        """Раскрывает или сворачивает панель.

        `notify` выключен для программного применения сохранённого состояния:
        там вызывающий сам решает, писать ли его на диск.
        """
        self.is_visible = visible
        self._sync_visibility()
        self.toggle_button.bgcolor = ft.Colors.TRANSPARENT
        self._update(self.panel, self.toggle_button, self.resize_handle)
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
        """Кладёт содержимое в прокручиваемую область панели."""
        self._content_host.controls = [content]
        self._update(self._content_host, self._scroll)


class ApplicationLayout:
    """5-panel layout: top, left (collapsible), workspace (center), right (collapsible), bottom."""

    def __init__(
        self,
        page: ft.Page,
        config: PanelConfig | None = None,
        on_panel_toggle: Callable[[str, bool], None] | None = None,
        on_panel_resize: Callable[[str, int], None] | None = None,
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
            min_width=self.config.min_panel_width,
            max_width=self.config.max_left_width,
            on_resize=on_panel_resize,
        )
        self.right_panel = CollapsiblePanel(
            page,
            position="right",
            default_width=self.config.right_width,
            collapsed=self.config.right_collapsed,
            on_toggle=on_panel_toggle,
            min_width=self.config.min_panel_width,
            max_width=self.config.max_right_width,
            on_resize=on_panel_resize,
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
                self.left_panel.resize_handle,
                self.left_panel.toggle_button,
                self.workspace_panel,
                self.right_panel.toggle_button,
                self.right_panel.resize_handle,
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
        две боковые панели (свёрнутая занимает ноль), по полосе тумблера и
        по полосе перетаскивания на каждую, плюс верхняя и нижняя панели
        по высоте.
        """
        side = 0.0
        for panel in (self.left_panel, self.right_panel):
            side += CollapsiblePanel.TOGGLE_WIDTH
            if panel.is_visible:
                side += RESIZE_HANDLE_WIDTH
                side += float(panel.current_width)
        return max(width - side, 0.0), max(
            height - self.config.top_height - self.config.bottom_height, 0.0
        )

    def panel_widths(self) -> tuple[int, int]:
        """Текущая ширина раскрытых боковых панелей (лев, прав)."""
        return self.left_panel.current_width, self.right_panel.current_width

    def set_max_panel_width(self, position: str, max_width: int) -> None:
        """Применяет новый верхний предел ширины панели (из настроек).

        Живое применение: пользователь поменял настройку — панель сразу
        подтягивается, если была шире.
        """
        panel = self.left_panel if position == "left" else self.right_panel
        panel.set_max_width(max_width)

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
